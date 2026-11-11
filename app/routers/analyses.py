"""Rotas de análise: tetos, pedido de análise, consulta do relatório e lista."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app import worker
from app.domain.errors import InvalidUrlError
from app.domain.features import ALGO_VERSION
from app.domain.notes import DEFAULT_CEILING_MIDI, ceiling_options
from app.domain.schemas import (
    AnalysisCreated,
    AnalysisOut,
    AnalysisRequest,
    AnalysisSummary,
    CeilingOut,
    CeilingsOut,
    JobOut,
)
from app.routers.deps import CurrentUserDep, Session, get_current_user
from app.services import jobs, ratelimit, store
from app.services.report import build_report, note_out
from app.services.youtube import parse_video_id

router = APIRouter(prefix="/api", tags=["analyses"], dependencies=[Depends(get_current_user)])


def _utc(moment: datetime) -> datetime:
    """As datas vêm do banco sem fuso; elas são sempre UTC."""
    return moment.replace(tzinfo=UTC)


@router.get(
    "/ceilings",
    summary="Lista os tetos disponíveis",
    description="Opções de tom teto (C3 a C5, dó central = C4) e a escolha padrão.",
)
def list_ceilings() -> CeilingsOut:
    """Opções da lista de teto."""
    options = [CeilingOut(midi=o.midi, name=o.name) for o in ceiling_options()]
    return CeilingsOut(options=options, default_midi=DEFAULT_CEILING_MIDI)


@router.post(
    "/analyses",
    summary="Pede a análise de uma música",
    description=(
        "Recebe o link do YouTube e põe a música na lista da pessoa. Se o vídeo já foi "
        "analisado (por qualquer pessoa), responde 200 com `already_analyzed` e a data, sem "
        "baixar de novo; senão responde 202 e enfileira para o worker. "
        "Com `extract_now`, a API tenta extrair antes de responder, por até 60 s (pelo proxy "
        "`PROXY_*`, se configurado) e, se não der, o job fica na fila para o worker. "
        "Responde 429 se a pessoa passou do limite de novos pedidos por hora."
    ),
)
async def create_analysis(
    body: AnalysisRequest,
    response: Response,
    session: Session,
    user: CurrentUserDep,
) -> AnalysisCreated:
    """Liga o vídeo à pessoa e reaproveita a análise ou o job; senão enfileira um novo."""
    try:
        video_id = parse_video_id(body.url)
    except InvalidUrlError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.message) from error
    row = await store.find(session, video_id)
    if row is not None and row.algo_version == ALGO_VERSION:
        await store.link(session, user.id, video_id)
        return AnalysisCreated(
            video_id=video_id, already_analyzed=True, analyzed_at=_utc(row.created_at)
        )
    progress = await jobs.get(session, video_id)
    if progress is None or progress.status == "error":  # só pedido novo conta no limite
        client = f"user:{user.id}"
        if ratelimit.exceeded(client):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Limite de pedidos por hora atingido, tente mais tarde.",
            )
        if await jobs.start(session, video_id):
            ratelimit.record(client)
            await store.link(session, user.id, video_id)
            if body.extract_now:
                await worker.extract_in_api(video_id)
    else:  # o job de outra pessoa (ou o seu) serve: só entra na lista
        await store.link(session, user.id, video_id)
    response.status_code = status.HTTP_202_ACCEPTED
    return AnalysisCreated(video_id=video_id, already_analyzed=False)


@router.get(
    "/analyses",
    summary="Lista as minhas músicas já analisadas",
    description=(
        "Só as da lista da pessoa, das mais recentes para as mais antigas, com título, "
        "duração e nota mais aguda."
    ),
)
async def list_analyses(session: Session, user: CurrentUserDep) -> list[AnalysisSummary]:
    """Resumo de cada análise pronta da lista da pessoa."""
    return [
        AnalysisSummary(
            video_id=row.video_id,
            title=row.title,
            duration_seconds=row.duration_seconds,
            top_note=note_out(row.top_midi),
            created_at=_utc(row.created_at),
        )
        for row in await store.list_for_user(session, user.id)
    ]


@router.get(
    "/analyses/{video_id}",
    summary="Consulta o relatório de uma música",
    description=(
        "Devolve o status (na fila, baixando, analisando, pronto ou erro) e, se pronto, o "
        "relatório calculado, sem baixar o áudio de novo. Sem `ceiling_midi` usa o teto salvo "
        "da pessoa; com ele, só pré-visualiza (não grava). 404 se a música não está na lista."
    ),
)
async def get_analysis(
    video_id: str,
    session: Session,
    user: CurrentUserDep,
    ceiling_midi: Annotated[int | None, Query(ge=48, le=72)] = None,
) -> AnalysisOut:
    """Estado da análise; 404 se a música não está na lista da pessoa."""
    if not await store.is_linked(session, user.id, video_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
    progress = await jobs.get(session, video_id)
    row = await store.find(session, video_id)
    # Erro de uma reanálise não esconde o registro guardado, que continua legível.
    if progress is not None and not (progress.status == "error" and row is not None):
        return AnalysisOut(video_id=video_id, status=progress.status, error=progress.error)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
    if ceiling_midi is None:
        ceiling_midi = await store.get_ceiling(session, user.id)
    report = build_report(store.to_features(row), ceiling_midi)
    return AnalysisOut(video_id=video_id, status="done", title=row.title, report=report)


@router.delete(
    "/analyses/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Tira uma música da minha lista",
    description=(
        "Remove só o vínculo da pessoa; as features compartilhadas ficam. Responde 404 se a "
        "música não está na lista e 409 se está sendo analisada agora."
    ),
)
async def delete_analysis(video_id: str, session: Session, user: CurrentUserDep) -> None:
    """Desliga a música da pessoa e esquece a falha dela se ninguém mais a tem."""
    if not await store.is_linked(session, user.id, video_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
    progress = await jobs.get(session, video_id)
    if progress is not None and progress.status != "error":
        raise HTTPException(status.HTTP_409_CONFLICT, "A música está sendo analisada agora.")
    await store.unlink(session, user.id, video_id)
    if not await store.has_links(session, video_id):
        await jobs.forget(session, video_id)


@router.get(
    "/jobs",
    summary="Lista os meus pedidos em andamento ou com erro",
    description=(
        "Pedidos da pessoa que ainda não viraram análise guardada: na fila, baixando, "
        "analisando ou com erro (com a mensagem). Do mais recente para o mais antigo."
    ),
)
async def list_jobs(session: Session, user: CurrentUserDep) -> list[JobOut]:
    """Fila e falhas, para a tela mostrar o que o worker está fazendo ou não conseguiu."""
    return [
        JobOut(
            video_id=job.video_id,
            status=job.status,
            error=job.error,
            updated_at=_utc(job.updated_at),
        )
        for job in await jobs.list_for_user(session, user.id)
    ]


@router.delete(
    "/jobs/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dispensa um pedido com erro",
    description=(
        "Tira a falha da lista da pessoa. Se a música já tem análise guardada, só some a "
        "falha; se não, o pedido sai da lista da pessoa. Responde 404 se a música não está na "
        "lista e 409 se o pedido está na fila ou em andamento."
    ),
)
async def dismiss_job(video_id: str, session: Session, user: CurrentUserDep) -> None:
    """Esquece a falha do vídeo para ela sair da lista de pedidos."""
    if not await store.is_linked(session, user.id, video_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado.")
    progress = await jobs.get(session, video_id)
    if progress is not None and progress.status != "error":
        raise HTTPException(status.HTTP_409_CONFLICT, "O pedido está na fila ou em andamento.")
    if await store.find(session, video_id) is None:  # pedido que nunca virou análise
        await store.unlink(session, user.id, video_id)
        if await store.has_links(session, video_id):
            return
    await jobs.forget(session, video_id)
