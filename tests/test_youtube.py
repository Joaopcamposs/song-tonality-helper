from pathlib import Path

import pytest
import yt_dlp

from app.domain.errors import DownloadError, InvalidUrlError, VideoTooLongError
from app.services import download, youtube

VIDEO_ID = "dQw4w9WgXcQ"


class FakeYoutubeDL:
    """Duplo do yt-dlp: devolve metadados fixos e grava um wav vazio ao baixar."""

    duration: float | None = 120
    error: Exception | None = None
    last_opts: dict = {}
    last_url: str = ""

    def __init__(self, opts: dict) -> None:
        FakeYoutubeDL.last_opts = opts
        self.opts = opts

    def __enter__(self) -> FakeYoutubeDL:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> dict:
        if self.error:
            raise self.error
        FakeYoutubeDL.last_url = url
        return {"duration": self.duration, "title": "Dois Passarinhos"}

    def download(self, urls: list[str]) -> None:
        dest = Path(self.opts["outtmpl"]).parent
        (dest / "audio.wav").write_bytes(b"RIFF")


@pytest.fixture(autouse=True)
def fake_ytdlp(monkeypatch):
    FakeYoutubeDL.duration = 120
    FakeYoutubeDL.error = None
    monkeypatch.setattr(download.yt_dlp, "YoutubeDL", FakeYoutubeDL)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=10",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ&list=RDAMVM",
        "http://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
    ],
)
def test_parse_video_id_accepts_all_link_forms(url):
    assert youtube.parse_video_id(url) == VIDEO_ID


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://evil.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
        "não é url",
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/@canal",
        "https://www.youtube.com/watch?v=curto",
    ],
)
def test_parse_video_id_rejects(url):
    with pytest.raises(InvalidUrlError):
        youtube.parse_video_id(url)


def test_download_returns_wav_and_metadata(tmp_path):
    audio = download.download_audio(VIDEO_ID, tmp_path)
    assert audio.path == tmp_path / "audio.wav"
    assert (audio.title, audio.duration_seconds) == ("Dois Passarinhos", 120)


def test_download_uses_canonical_url(tmp_path):
    download.download_audio(VIDEO_ID, tmp_path)
    assert FakeYoutubeDL.last_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_download_rejects_long_video(tmp_path):
    FakeYoutubeDL.duration = download.MAX_DURATION_SECONDS + 1
    with pytest.raises(VideoTooLongError):
        download.download_audio(VIDEO_ID, tmp_path)
    assert not (tmp_path / "audio.wav").exists()


def test_download_rejects_unknown_duration(tmp_path):
    FakeYoutubeDL.duration = None
    with pytest.raises(DownloadError):
        download.download_audio(VIDEO_ID, tmp_path)


def test_download_wraps_ytdlp_errors(tmp_path):
    FakeYoutubeDL.error = yt_dlp.utils.DownloadError("boom")
    with pytest.raises(DownloadError):
        download.download_audio(VIDEO_ID, tmp_path)


def test_download_disables_playlist(tmp_path):
    download.download_audio(VIDEO_ID, tmp_path)
    assert FakeYoutubeDL.last_opts["noplaylist"] is True


@pytest.mark.parametrize(
    ("url", "word"),
    [
        ("https://www.youtube.com/@canal", "canal"),
        ("https://www.youtube.com/channel/UC123", "canal"),
        ("https://www.youtube.com/playlist?list=PL123", "playlist"),
    ],
)
def test_parse_video_id_explains_channel_and_playlist_links(url, word):
    with pytest.raises(InvalidUrlError, match=word):
        youtube.parse_video_id(url)


def test_download_passes_proxy_only_when_given(tmp_path):
    download.download_audio(VIDEO_ID, tmp_path)
    assert "proxy" not in FakeYoutubeDL.last_opts
    download.download_audio(VIDEO_ID, tmp_path, proxy="http://u:p@proxy.exemplo:8080")
    assert FakeYoutubeDL.last_opts["proxy"] == "http://u:p@proxy.exemplo:8080"


def test_download_error_log_hides_proxy(tmp_path, caplog):
    proxy = "http://usuario:segredo123@proxy.exemplo:8080"
    FakeYoutubeDL.error = yt_dlp.utils.DownloadError(f"falha via {proxy}")
    with pytest.raises(DownloadError) as raised:
        download.download_audio(VIDEO_ID, tmp_path, proxy=proxy)
    assert "segredo123" not in caplog.text
    assert "segredo123" not in raised.value.message


def test_download_uses_system_ffmpeg_or_bundled(tmp_path, monkeypatch):
    monkeypatch.setattr(download.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    download.download_audio(VIDEO_ID, tmp_path)
    assert "ffmpeg_location" not in FakeYoutubeDL.last_opts
    monkeypatch.setattr(download.shutil, "which", lambda name: None)
    monkeypatch.setattr(download.imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/pacote/ffmpeg")
    download.download_audio(VIDEO_ID, tmp_path)
    assert FakeYoutubeDL.last_opts["ffmpeg_location"] == "/pacote/ffmpeg"
