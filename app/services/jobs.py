"""Andamento das análises em memória e execução em segundo plano."""

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.domain.errors import DomainError
from app.domain.pitch import ALGO_VERSION, AudioFeatures, analyze_audio
from app.services import store
from app.services.youtube import DownloadedAudio, download_audio

logger = logging.getLogger(__name__)

MAX_JOBS = 50


@dataclass
class Progress:
    """Andamento de uma análise ainda não gravada: em curso ou que falhou."""

    status: Literal["downloading", "analyzing", "error"]
    error: str | None = None


# Dicionário preserva a ordem de inserção: o primeiro item é o mais antigo.
_progress: dict[str, Progress] = {}


def start(video_id: str) -> bool:
    """Marca o vídeo como em andamento; devolve False se já estava em análise."""
    current = _progress.get(video_id)
    if current is not None and current.status != "error":
        return False
    _progress.pop(video_id, None)
    _progress[video_id] = Progress("downloading")
    while len(_progress) > MAX_JOBS:
        # Só descarta falhas antigas: análise em curso nunca some do andamento.
        stale = next((key for key, p in _progress.items() if p.status == "error"), None)
        if stale is None:
            break
        del _progress[stale]
    return True


def get(video_id: str) -> Progress | None:
    """Andamento do vídeo, se estiver em análise ou tiver falhado."""
    return _progress.get(video_id)


def _analyze(video_id: str) -> tuple[DownloadedAudio, AudioFeatures]:
    """Baixa e analisa o áudio (bloqueante); o arquivo temporário é sempre apagado."""
    with tempfile.TemporaryDirectory() as tmp:
        audio = download_audio(video_id, Path(tmp))
        _progress[video_id].status = "analyzing"
        return audio, analyze_audio(audio.path)


async def run(video_id: str) -> None:
    """Executa a análise e grava o resultado; em falha, guarda só a mensagem de erro."""
    try:
        async with store.session() as session:
            row = await store.find(session, video_id)
        if row is not None and row.algo_version == ALGO_VERSION:  # outro pedido já terminou
            del _progress[video_id]
            return
        audio, features = await asyncio.to_thread(_analyze, video_id)
        async with store.session() as session:
            await store.save(session, video_id, audio.title, audio.duration_seconds, features)
        del _progress[video_id]
    except DomainError as error:
        _progress[video_id] = Progress("error", error.message)
    except Exception:
        logger.exception("Falha inesperada na análise %s", video_id)
        _progress[video_id] = Progress("error", "Erro inesperado ao analisar a música.")
