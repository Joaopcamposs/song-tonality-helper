"""Worker local: puxa jobs pendentes do banco, baixa o áudio, analisa e grava o resultado.

Uso: `python -m app.worker`. Rode um único worker por banco.
"""

import asyncio
import contextlib
import logging
import os
import signal

from app.services import jobs, store

logger = logging.getLogger(__name__)


async def process_next() -> bool:
    """Reivindica e executa um job pendente; devolve False se a fila está vazia."""
    async with store.session() as session:
        video_id = await jobs.claim(session)
    if video_id is None:
        return False
    logger.info("Analisando %s", video_id)
    await jobs.run(video_id)
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
