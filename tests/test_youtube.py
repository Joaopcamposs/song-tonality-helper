from pathlib import Path

import pytest
import yt_dlp

from app.domain.errors import DownloadError, InvalidUrlError, VideoTooLongError
from app.services import youtube

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
    monkeypatch.setattr(youtube.yt_dlp, "YoutubeDL", FakeYoutubeDL)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=10",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ&list=RDAMVM",
        "http://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
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
    audio = youtube.download_audio(VIDEO_ID, tmp_path)
    assert audio.path == tmp_path / "audio.wav"
    assert (audio.title, audio.duration_seconds) == ("Dois Passarinhos", 120)


def test_download_uses_canonical_url(tmp_path):
    youtube.download_audio(VIDEO_ID, tmp_path)
    assert FakeYoutubeDL.last_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_download_rejects_long_video(tmp_path):
    FakeYoutubeDL.duration = youtube.MAX_DURATION_SECONDS + 1
    with pytest.raises(VideoTooLongError):
        youtube.download_audio(VIDEO_ID, tmp_path)
    assert not (tmp_path / "audio.wav").exists()


def test_download_rejects_unknown_duration(tmp_path):
    FakeYoutubeDL.duration = None
    with pytest.raises(DownloadError):
        youtube.download_audio(VIDEO_ID, tmp_path)


def test_download_wraps_ytdlp_errors(tmp_path):
    FakeYoutubeDL.error = yt_dlp.utils.DownloadError("boom")
    with pytest.raises(DownloadError):
        youtube.download_audio(VIDEO_ID, tmp_path)


def test_download_disables_playlist(tmp_path):
    youtube.download_audio(VIDEO_ID, tmp_path)
    assert FakeYoutubeDL.last_opts["noplaylist"] is True
