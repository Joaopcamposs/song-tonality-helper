"""Download do áudio com o yt-dlp, opcionalmente por um proxy."""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import imageio_ffmpeg
import yt_dlp

from app.domain.errors import DownloadError, VideoTooLongError

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 600
SOCKET_TIMEOUT_SECONDS = 20  # evita que uma conexão muda deixe o download pendurado


@dataclass(frozen=True)
class DownloadedAudio:
    """Áudio baixado e os metadados do vídeo."""

    path: Path
    title: str
    duration_seconds: int


def redact(text: str, secret: str | None) -> str:
    """Troca por `***` a URL do proxy, o usuário (`customer-...`) e a senha, crua e codificada."""
    if not secret:
        return text
    parts = urlsplit(secret)
    hidden = [secret, parts.username, parts.password]
    hidden.append(unquote(parts.password) if parts.password else None)
    # Mais longos primeiro, para a URL inteira sumir antes de seus pedaços.
    for item in sorted(filter(None, hidden), key=len, reverse=True):
        text = text.replace(item, "***")
    return text


def download_audio(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
    """Baixa só o áudio como `audio.wav` em `dest_dir` e devolve o caminho e os metadados.

    Com `proxy`, o yt-dlp sai por ele; a URL é segredo e nunca vai para log ou mensagem de erro.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    options = {
        "noplaylist": True,
        "allowed_extractors": ["youtube"],
        "socket_timeout": SOCKET_TIMEOUT_SECONDS,
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "audio.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    }
    if proxy:
        options["proxy"] = proxy
    if shutil.which("ffmpeg") is None:  # sem ffmpeg no sistema (ex.: nuvem), usa o do pacote
        options["ffmpeg_location"] = imageio_ffmpeg.get_ffmpeg_exe()
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
        logger.warning("Falha do yt-dlp: %s", redact(str(error), proxy))
        raise DownloadError("Não consegui baixar o áudio deste vídeo.") from None

    path = dest_dir / "audio.wav"
    if not path.exists():
        raise DownloadError("O download terminou, mas o áudio não foi gerado.")
    return DownloadedAudio(path, info.get("title") or video_id, int(duration))
