"""Worker local (único que usa yt-dlp e librosa): processa os jobs pendentes do banco.

Baixa o áudio, analisa e grava o resultado.

Uso: `python -m app.worker`. Rode um único worker por banco.
"""

import asyncio
import contextlib
import logging
import os
import signal
import tempfile
from pathlib import Path

from sqlalchemy import delete, update

from app.domain.errors import DomainError
from app.domain.features import ALGO_VERSION
from app.domain.pitch import analyze_audio
from app.services import jobs, store
from app.services.download import download_audio
from app.services.store import Job, JobStatus

logger = logging.getLogger(__name__)


async def _set_status(video_id: str, status: JobStatus) -> None:
    """Atualiza a etapa do job."""
    async with store.session() as session:
        await session.execute(
            update(Job).where(Job.video_id == video_id).values(status=status, updated_at=jobs.now())
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
        await jobs.fail(session, video_id, message)


async def run(video_id: str) -> None:
    """Executa um job já reivindicado e grava o resultado; em falha, guarda só o erro."""
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


async def process_next() -> bool:
    """Reivindica e executa um job pendente; devolve False se a fila está vazia."""
    async with store.session() as session:
        video_id = await jobs.claim(session)
    if video_id is None:
        return False
    logger.info("Analisando %s", video_id)
    await run(video_id)
    return True


async def recover_orphans() -> None:
    """Recoloca na fila jobs que ficaram em curso quando o worker anterior caiu."""
    async with store.session() as session:
        count = await jobs.requeue_orphans(session)
    if count:
        logger.warning("%d job(s) interrompido(s) voltaram para a fila", count)


async def run_once(needs_recovery: bool) -> tuple[bool, bool]:
    """Um passo do laço: devolve (havia job, precisa recuperar jobs presos).

    Se uma falha (ex.: banco fora do ar) deixar um job preso em curso, o passo seguinte o
    devolve à fila antes de consultar de novo.
    """
    try:
        if needs_recovery:
            await recover_orphans()
        return await process_next(), False
    except Exception:
        logger.exception("Falha ao processar a fila")
        return False, True


async def main() -> None:
    """Prepara o banco e processa a fila até receber SIGINT ou SIGTERM."""
    store.configure(store.database_url())
    poll = float(os.environ.get("WORKER_POLL_SECONDS", "5"))
    await store.create_tables()
    await recover_orphans()
    needs_recovery = False
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    logger.info("Worker no ar; consultando a fila a cada %.1fs", poll)
    while not stop.is_set():
        busy, needs_recovery = await run_once(needs_recovery)
        if not busy:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), poll)
    await store.dispose()
    logger.info("Worker encerrado")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(main())
