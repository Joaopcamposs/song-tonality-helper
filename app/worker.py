"""Worker: processa os jobs pendentes do banco (baixa o áudio, analisa e grava o resultado).

Uso: `python -m app.worker`. Rode um único worker por banco. A API também pode extrair um job
na hora (`extract_in_api`, pedido com `extract_now`), em até `EXTRACT_TIMEOUT_SECONDS`, pelo
proxy de `PROXY_*` se houver; se falhar ou estourar o prazo, o worker assume.
"""

import asyncio
import contextlib
import logging
import os
import signal
import tempfile
from pathlib import Path

from sqlalchemy import delete

from app.domain.errors import DomainError, DownloadError
from app.domain.features import ALGO_VERSION, AudioFeatures
from app.domain.pitch import analyze_audio
from app.services import jobs, store
from app.services.download import DownloadedAudio, download_audio, redact
from app.services.proxy import ProxyConfig
from app.services.store import Job

logger = logging.getLogger(__name__)

EXTRACT_TIMEOUT_SECONDS = 60  # prazo de toda a extração (download + análise) feita pela API


async def _finish(video_id: str) -> None:
    """Apaga o job concluído."""
    async with store.session() as session:
        await session.execute(delete(Job).where(Job.video_id == video_id))
        await session.commit()


async def _fail(video_id: str, message: str) -> None:
    """Abre uma sessão própria para registrar a falha."""
    async with store.session() as session:
        await jobs.fail(session, video_id, message)


def proxy_url() -> str | None:
    """URL do proxy de download (segredo); None quando as credenciais `PROXY_*` faltam.

    Com sessão sticky, cada chamada gera uma URL nova: chame uma vez por tentativa.
    """
    config = ProxyConfig.from_env(os.environ)
    return config.url() if config else None


async def _requeue(video_id: str) -> None:
    """Devolve o job à fila, sem erro visível, para o worker local assumir."""
    async with store.session() as session:
        await jobs.requeue(session, video_id)


def _extract(video_id: str, proxy: str | None) -> tuple[DownloadedAudio, AudioFeatures]:
    """Baixa e analisa o áudio; roda numa thread, que é dona do diretório temporário.

    A thread não pode ser cancelada: se o prazo estourar, ela termina sozinha, apaga o áudio
    e o resultado é descartado. Por isso nada é gravado aqui.
    """
    with tempfile.TemporaryDirectory() as tmp:
        audio = download_audio(video_id, Path(tmp), proxy)
        return audio, analyze_audio(audio.path)


async def run(
    video_id: str, proxy: str | None = None, in_api: bool = False, timeout: float | None = None
) -> None:
    """Executa um job já reivindicado e grava o resultado; em falha, guarda só o erro.

    Com `in_api` (extração feita pela API), falha de download, erro inesperado ou estouro de
    `timeout` devolvem o job à fila em vez de virar erro: o áudio pode estar bloqueado só ali, e
    o worker local tenta de novo (se também falhar lá, o erro aparece normalmente). Erros de
    análise seguem o caminho normal, pois o áudio seria o mesmo em qualquer lugar. A gravação só
    acontece aqui, depois do prazo, então o resultado tardio de uma thread nunca é gravado.
    """
    try:
        async with store.session() as session:
            row = await store.find(session, video_id)
        if row is not None and row.algo_version == ALGO_VERSION:  # outro pedido já terminou
            await _finish(video_id)
            return
        audio, features = await asyncio.wait_for(
            asyncio.to_thread(_extract, video_id, proxy), timeout
        )
        async with store.session() as session:
            await store.save(session, video_id, audio.title, audio.duration_seconds, features)
        await _finish(video_id)
        logger.info("Análise %s resolvida %s", video_id, "via proxy" if proxy else "via worker")
    except TimeoutError:
        if in_api:
            logger.warning("Extração de %s passou do prazo; fallback para o worker", video_id)
            await _requeue(video_id)
        else:
            logger.exception("Tempo esgotado na análise %s", video_id)
            await _fail(video_id, "Erro inesperado ao analisar a música.")
    except DomainError as error:
        if in_api and isinstance(error, DownloadError):
            logger.warning("Download de %s falhou na API; fallback para o worker", video_id)
            await _requeue(video_id)
        else:
            await _fail(video_id, error.message)
    except Exception as error:
        # Sem traceback quando há proxy: a mensagem da exceção pode conter a URL (segredo).
        if proxy is None and not in_api:
            logger.exception("Falha inesperada na análise %s", video_id)
            await _fail(video_id, "Erro inesperado ao analisar a música.")
        else:
            logger.error(
                "Falha inesperada na API em %s (%s: %s); fallback para o worker acionado",
                video_id,
                type(error).__name__,
                redact(str(error), proxy),
            )
            await _requeue(video_id)


async def process_next() -> bool:
    """Reivindica e executa um job pendente; devolve False se a fila está vazia."""
    async with store.session() as session:
        video_id = await jobs.claim(session)
    if video_id is None:
        return False
    logger.info("Analisando %s", video_id)
    await run(video_id)
    return True


async def extract_in_api(video_id: str) -> None:
    """Extrai o job na própria API (pedido com `extract_now`), com prazo de 60 s.

    Usa o proxy `PROXY_*` se configurado, senão sai direto. Não faz nada se o worker já o pegou.
    """
    async with store.session() as session:
        claimed = await jobs.claim(session, video_id)
    if claimed is None:
        return
    proxy = proxy_url()
    logger.info("Extraindo %s na API %s", video_id, "pelo proxy" if proxy else "direto")
    await run(video_id, proxy, in_api=True, timeout=EXTRACT_TIMEOUT_SECONDS)


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
