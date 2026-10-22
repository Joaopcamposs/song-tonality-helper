"""Validação de links do YouTube e download do áudio com o yt-dlp."""

import logging
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from app.domain.errors import DownloadError, InvalidUrlError, VideoTooLongError

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 600
_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def validate_url(url: str) -> str:
    """Aceita só links http(s) de hosts do YouTube; devolve a URL ou levanta erro."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _ALLOWED_HOSTS:
        raise InvalidUrlError("Informe um link de vídeo do YouTube.")
    return url.strip()


def download_audio(url: str, dest_dir: Path) -> Path:
    """Baixa só o áudio do vídeo como `audio.wav` em `dest_dir` e devolve o caminho."""
    url = validate_url(url)
    options = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "audio.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration")
            if duration is None:
                raise DownloadError("Não consegui saber a duração do vídeo (transmissão ao vivo?).")
            if duration > MAX_DURATION_SECONDS:
                raise VideoTooLongError(
                    f"O vídeo passa de {MAX_DURATION_SECONDS // 60} minutos; use um mais curto."
                )
            ydl.download([url])
    except yt_dlp.utils.YoutubeDLError as error:
        logger.warning("Falha do yt-dlp: %s", error)
        raise DownloadError("Não consegui baixar o áudio deste vídeo.") from error

    path = dest_dir / "audio.wav"
    if not path.exists():
        raise DownloadError("O download terminou, mas o áudio não foi gerado.")
    return path
