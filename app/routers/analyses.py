"""Rotas de análise: tetos, pedido de análise, consulta do relatório e lista."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import InvalidUrlError
from app.domain.notes import DEFAULT_CEILING_MIDI, ceiling_options
from app.domain.pitch import ALGO_VERSION
from app.domain.schemas import (
    AnalysisCreated,
    AnalysisOut,
    AnalysisRequest,
    AnalysisSummary,
    CeilingOut,
    CeilingsOut,
)
from app.services import jobs, ratelimit, store
from app.services.auth import require_passphrase
from app.services.report import build_report, note_out
from app.services.youtube import parse_video_id

router = APIRouter(prefix="/api", tags=["analyses"], dependencies=[Depends(require_passphrase)])

Session = Annotated[AsyncSession, Depends(store.get_session)]


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
        "Recebe o link do YouTube. Se o vídeo já foi analisado, responde 200 com "
        "`already_analyzed` e a data; senão responde 202 e enfileira para o worker. "
        "Responde 429 se o IP passou do limite de novos pedidos por hora."
    ),
)
async def create_analysis(
    body: AnalysisRequest, request: Request, response: Response, session: Session
) -> AnalysisCreated:
    """Identifica o vídeo, reaproveita a análise guardada ou enfileira uma nova."""
    try:
        video_id = parse_video_id(body.url)
    except InvalidUrlError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.message) from error
    row = await store.find(session, video_id)
    if row is not None and row.algo_version == ALGO_VERSION:
        return AnalysisCreated(
            video_id=video_id, already_analyzed=True, analyzed_at=_utc(row.created_at)
        )
    progress = await jobs.get(session, video_id)
    if progress is None or progress.status == "error":  # só pedido novo conta no limite
        client = ratelimit.client_ip(request)
        if ratelimit.exceeded(client):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Limite de pedidos por hora atingido, tente mais tarde.",
            )
        if await jobs.start(session, video_id):
            ratelimit.record(client)
    response.status_code = status.HTTP_202_ACCEPTED
    return AnalysisCreated(video_id=video_id, already_analyzed=False)


@router.get(
    "/analyses",
    summary="Lista as músicas já analisadas",
    description="Das mais recentes para as mais antigas, com título, duração e nota mais aguda.",
)
async def list_analyses(session: Session) -> list[AnalysisSummary]:
    """Resumo de cada análise guardada."""
    return [
        AnalysisSummary(
            video_id=row.video_id,
            title=row.title,
            duration_seconds=row.duration_seconds,
            top_note=note_out(row.top_midi),
            created_at=_utc(row.created_at),
        )
        for row in await store.list_recent(session)
    ]


@router.get(
    "/analyses/{video_id}",
    summary="Consulta o relatório de uma música",
    description=(
        "Devolve o status (na fila, baixando, analisando, pronto ou erro) e, se pronto, o "
        "relatório calculado para o `ceiling_midi` pedido, sem baixar o áudio de novo."
    ),
)
async def get_analysis(
    video_id: str,
    session: Session,
    ceiling_midi: Annotated[int, Query(ge=48, le=72)] = DEFAULT_CEILING_MIDI,
) -> AnalysisOut:
    """Estado da análise; 404 se o vídeo nunca foi analisado."""
    progress = await jobs.get(session, video_id)
    row = await store.find(session, video_id)
    # Erro de uma reanálise não esconde o registro guardado, que continua legível.
    if progress is not None and not (progress.status == "error" and row is not None):
        return AnalysisOut(video_id=video_id, status=progress.status, error=progress.error)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
    report = build_report(store.to_features(row), ceiling_midi)
    return AnalysisOut(video_id=video_id, status="done", title=row.title, report=report)


@router.delete(
    "/analyses/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Apaga uma música da lista",
    description=(
        "Remove a análise guardada. Responde 404 se não existe e 409 se a música está "
        "sendo analisada agora."
    ),
)
async def delete_analysis(video_id: str, session: Session) -> None:
    """Apaga a análise guardada e a falha registrada do vídeo."""
    if not await jobs.forget(session, video_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "A música está sendo analisada agora.")
    if not await store.remove(session, video_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
