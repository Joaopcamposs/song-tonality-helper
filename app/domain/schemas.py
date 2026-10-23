"""Modelos Pydantic da API: pedido de análise, andamento, lista e relatório."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NoteOut(BaseModel):
    """Uma nota com oitava (dó central = C4)."""

    midi: int
    name: str


class RankedNote(BaseModel):
    """Uma nota do ranking e quantos quadros ela ocupou."""

    note: NoteOut
    frames: int


class KeyOut(BaseModel):
    """Um tom candidato e a correlação que ele obteve."""

    tonic: str
    mode: Literal["maior", "menor"]
    score: float


class Report(BaseModel):
    """Relatório final da análise de uma música."""

    top_note: NoteOut
    ceiling: NoteOut
    ranking: list[RankedNote]
    top_times: list[float]
    keys: list[KeyOut]
    shift: int
    alternative_shift: int
    new_key: str
    scale_degree: str
    new_top_note: NoteOut


class AnalysisRequest(BaseModel):
    """Pedido de análise: link do YouTube. O teto só entra na consulta do relatório."""

    url: str
    extract_now: bool = Field(
        default=False,
        description=(
            "False (padrão): só enfileira para o worker. True: a própria API tenta extrair "
            "antes de responder, por até 60 s (pelo proxy `PROXY_*`, se configurado); se não "
            "terminar, o job volta à fila para o worker."
        ),
    )


class AnalysisCreated(BaseModel):
    """Resposta do pedido: id do vídeo e se ele já estava analisado."""

    video_id: str
    already_analyzed: bool
    analyzed_at: datetime | None = None


class AnalysisOut(BaseModel):
    """Estado de uma análise; o relatório vem quando o status é `done`."""

    video_id: str
    status: Literal["pending", "downloading", "analyzing", "done", "error"]
    error: str | None = None
    title: str | None = None
    report: Report | None = None


class AnalysisSummary(BaseModel):
    """Item da lista de músicas já analisadas."""

    video_id: str
    title: str
    duration_seconds: int
    top_note: NoteOut
    created_at: datetime


class JobOut(BaseModel):
    """Pedido ainda sem análise guardada: na fila, em curso ou com erro."""

    video_id: str
    status: Literal["pending", "downloading", "analyzing", "error"]
    error: str | None = None
    updated_at: datetime


class CeilingOut(BaseModel):
    """Uma opção da lista de teto."""

    midi: int
    name: str


class CeilingsOut(BaseModel):
    """Opções da lista de teto e a escolha padrão."""

    options: list[CeilingOut]
    default_midi: int
