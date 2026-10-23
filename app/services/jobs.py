"""Andamento das análises guardado no banco: fila e reivindicação (a execução fica no worker)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.store import Job, JobStatus

MAX_JOBS = 50


@dataclass
class Progress:
    """Andamento de uma análise ainda não gravada: em curso ou que falhou."""

    status: JobStatus
    error: str | None = None


def now() -> datetime:
    """Momento atual em UTC, sem fuso, como o banco guarda."""
    return datetime.now(UTC).replace(tzinfo=None)


async def start(session: AsyncSession, video_id: str) -> bool:
    """Enfileira o vídeo como `pending`; devolve False se já havia job em curso."""
    # O UPDATE condicional reaproveita só a linha de falha, mesmo com pedidos simultâneos.
    reused = await session.execute(
        update(Job)
        .where(Job.video_id == video_id, Job.status == "error")
        .values(status="pending", error=None, updated_at=now())
    )
    assert isinstance(reused, CursorResult)
    if reused.rowcount == 0:
        session.add(Job(video_id=video_id, status="pending", error=None, updated_at=now()))
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
        .values(status="error", error=message, updated_at=now())
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


async def claim(session: AsyncSession) -> str | None:
    """Reivindica o job `pending` mais antigo, passando-o a `downloading`; None se não há fila."""
    oldest = (
        select(Job.video_id)
        .where(Job.status == "pending")
        .order_by(Job.updated_at)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    # A condição repetida no UPDATE garante que só um worker ganha cada job.
    claimed = await session.scalar(
        update(Job)
        .where(Job.video_id == oldest, Job.status == "pending")
        .values(status="downloading", updated_at=now())
        .returning(Job.video_id)
    )
    await session.commit()
    return claimed


async def requeue_orphans(session: AsyncSession) -> int:
    """Recoloca na fila os jobs em curso de um worker que caiu; devolve quantos eram."""
    result = await session.execute(
        update(Job)
        .where(Job.status.in_(("downloading", "analyzing")))
        .values(status="pending", updated_at=now())
    )
    assert isinstance(result, CursorResult)
    await session.commit()
    return result.rowcount
