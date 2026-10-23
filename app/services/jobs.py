"""Andamento das análises guardado no banco e execução em segundo plano."""

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.domain.pitch import ALGO_VERSION, analyze_audio
from app.services import store
from app.services.store import Job, JobStatus
from app.services.youtube import download_audio

logger = logging.getLogger(__name__)

MAX_JOBS = 50
INTERRUPTED_MESSAGE = "Análise interrompida, tente de novo."


@dataclass
class Progress:
    """Andamento de uma análise ainda não gravada: em curso ou que falhou."""

    status: JobStatus
    error: str | None = None


def _now() -> datetime:
    """Momento atual em UTC, sem fuso, como o banco guarda."""
    return datetime.now(UTC).replace(tzinfo=None)


async def start(session: AsyncSession, video_id: str) -> bool:
    """Marca o vídeo como em andamento; devolve False se já havia job em curso."""
    # O UPDATE condicional reaproveita só a linha de falha, mesmo com pedidos simultâneos.
    reused = await session.execute(
        update(Job)
        .where(Job.video_id == video_id, Job.status == "error")
        .values(status="downloading", error=None, updated_at=_now())
    )
    assert isinstance(reused, CursorResult)
    if reused.rowcount == 0:
        session.add(Job(video_id=video_id, status="downloading", error=None, updated_at=_now()))
    try:
        await session.commit()
    except IntegrityError:  # outro pedido criou o job antes
        await session.rollback()
        return False
    await _prune(session)
    return True


async def _prune(session: AsyncSession) -> None:
    """Mantém no máximo `MAX_JOBS` falhas, descartando as mais antigas; job em curso fica."""
    stale = await session.scalars(
        select(Job.video_id)
        .where(Job.status == "error")
        .order_by(Job.updated_at.desc())
        .offset(MAX_JOBS)
    )
    ids = list(stale)
    if ids:
        await session.execute(delete(Job).where(Job.video_id.in_(ids)))
        await session.commit()


async def fail(session: AsyncSession, video_id: str, message: str) -> None:
    """Marca o job como falho, guardando a mensagem para a tela."""
    await session.execute(
        update(Job)
        .where(Job.video_id == video_id)
        .values(status="error", error=message, updated_at=_now())
    )
    await session.commit()
    await _prune(session)


async def forget(session: AsyncSession, video_id: str) -> bool:
    """Esquece a falha guardada do vídeo; devolve False se há análise em curso."""
    job = await session.get(Job, video_id)
    if job is None:
        return True
    if job.status != "error":
        return False
    await session.delete(job)
    await session.commit()
    return True


async def get(session: AsyncSession, video_id: str) -> Progress | None:
    """Andamento do vídeo, se estiver em análise ou tiver falhado."""
    job = await session.get(Job, video_id)
    return None if job is None else Progress(job.status, job.error)


async def fail_interrupted() -> None:
    """Marca como falho todo job em curso; roda na subida, quando nenhum processo o executa."""
    async with store.session() as session:
        await session.execute(
            update(Job)
            .where(Job.status != "error")
            .values(status="error", error=INTERRUPTED_MESSAGE, updated_at=_now())
        )
        await session.commit()


async def _set_status(video_id: str, status: JobStatus) -> None:
    """Atualiza a etapa do job."""
    async with store.session() as session:
        await session.execute(
            update(Job).where(Job.video_id == video_id).values(status=status, updated_at=_now())
        )
        await session.commit()


async def _finish(video_id: str) -> None:
    """Apaga o job concluído."""
    async with store.session() as session:
        await session.execute(delete(Job).where(Job.video_id == video_id))
        await session.commit()


async def _fail(video_id: str, message: str) -> None:
    """Abre uma sessão própria para registrar a falha."""
    async with store.session() as session:
        await fail(session, video_id, message)


async def run(video_id: str) -> None:
    """Executa a análise e grava o resultado; em falha, guarda só a mensagem de erro."""
    try:
        async with store.session() as session:
            row = await store.find(session, video_id)
        if row is not None and row.algo_version == ALGO_VERSION:  # outro pedido já terminou
            await _finish(video_id)
            return
        with tempfile.TemporaryDirectory() as tmp:  # o áudio é sempre apagado
            audio = await asyncio.to_thread(download_audio, video_id, Path(tmp))
            await _set_status(video_id, "analyzing")
            features = await asyncio.to_thread(analyze_audio, audio.path)
        async with store.session() as session:
            await store.save(session, video_id, audio.title, audio.duration_seconds, features)
        await _finish(video_id)
    except DomainError as error:
        await _fail(video_id, error.message)
    except Exception:
        logger.exception("Falha inesperada na análise %s", video_id)
        await _fail(video_id, "Erro inesperado ao analisar a música.")
