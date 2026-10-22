from pathlib import Path

import pytest
import yt_dlp

from app.domain.errors import DownloadError, InvalidUrlError, VideoTooLongError
from app.services import youtube

VALID = "https://www.youtube.com/watch?v=abc123"


class FakeYoutubeDL:
    """Duplo do yt-dlp: devolve metadados fixos e grava um wav vazio ao baixar."""

    duration: float | None = 120
    info_type: str = "video"
    error: Exception | None = None
    last_opts: dict = {}

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
        if self.info_type == "playlist":
            return {"_type": "playlist", "entries": []}
        return {"duration": self.duration}

    def download(self, urls: list[str]) -> None:
        dest = Path(self.opts["outtmpl"]).parent
        (dest / "audio.wav").write_bytes(b"RIFF")


@pytest.fixture(autouse=True)
def fake_ytdlp(monkeypatch):
    FakeYoutubeDL.duration = 120
    FakeYoutubeDL.error = None
    FakeYoutubeDL.info_type = "video"
    monkeypatch.setattr(youtube.yt_dlp, "YoutubeDL", FakeYoutubeDL)


@pytest.mark.parametrize(
    "url",
    [
        VALID,
        "https://youtu.be/abc123",
        "https://music.youtube.com/watch?v=abc",
        "http://m.youtube.com/watch?v=abc",
    ],
)
def test_validate_url_accepts_youtube_hosts(url):
    assert youtube.validate_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://evil.com/watch?v=x",
        "https://youtube.com.evil.com/a",
        "não é url",
    ],
)
def test_validate_url_rejects_other_hosts_and_schemes(url):
    with pytest.raises(InvalidUrlError):
        youtube.validate_url(url)


def test_download_returns_wav_in_dest_dir(tmp_path):
    assert youtube.download_audio(VALID, tmp_path) == tmp_path / "audio.wav"


def test_download_rejects_long_video(tmp_path):
    FakeYoutubeDL.duration = youtube.MAX_DURATION_SECONDS + 1
    with pytest.raises(VideoTooLongError):
        youtube.download_audio(VALID, tmp_path)
    assert not (tmp_path / "audio.wav").exists()


def test_download_rejects_unknown_duration(tmp_path):
    FakeYoutubeDL.duration = None
    with pytest.raises(DownloadError):
        youtube.download_audio(VALID, tmp_path)


def test_download_wraps_ytdlp_errors(tmp_path):
    FakeYoutubeDL.error = yt_dlp.utils.DownloadError("boom")
    with pytest.raises(DownloadError):
        youtube.download_audio(VALID, tmp_path)


def test_download_disables_playlist(tmp_path):
    youtube.download_audio(VALID, tmp_path)
    assert FakeYoutubeDL.last_opts["noplaylist"] is True


def test_download_rejects_playlist_and_channel_links(tmp_path):
    FakeYoutubeDL.info_type = "playlist"
    with pytest.raises(InvalidUrlError):
        youtube.download_audio("https://www.youtube.com/playlist?list=PL123", tmp_path)
    assert not (tmp_path / "audio.wav").exists()


def test_download_resolves_playlists_only_flat(tmp_path):
    youtube.download_audio(VALID, tmp_path)
    assert FakeYoutubeDL.last_opts["extract_flat"] == "in_playlist"
