"""Download do áudio com o yt-dlp. Só o worker importa este módulo."""

import logging
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from app.domain.errors import DownloadError, VideoTooLongError

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 600


@dataclass(frozen=True)
class DownloadedAudio:
    """Áudio baixado e os metadados do vídeo."""

    path: Path
    title: str
    duration_seconds: int


def download_audio(video_id: str, dest_dir: Path) -> DownloadedAudio:
    """Baixa só o áudio como `audio.wav` em `dest_dir` e devolve o caminho e os metadados."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    options = {
        "noplaylist": True,
        "allowed_extractors": ["youtube"],
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
    return DownloadedAudio(path, info.get("title") or video_id, int(duration))
