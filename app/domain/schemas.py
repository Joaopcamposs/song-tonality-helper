"""Modelos Pydantic da API: pedido de análise, job e relatório."""

from typing import Literal

from pydantic import BaseModel, Field


class NoteOut(BaseModel):
    """Uma nota nas duas numerações de oitava."""

    midi: int
    user: str
    standard: str


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
    """Pedido de análise: link do YouTube e teto em MIDI (padrão), de C2 a C4 do usuário."""

    url: str
    ceiling_midi: int = Field(ge=48, le=72)


class JobCreated(BaseModel):
    """Resposta da criação de um job."""

    id: str


class JobOut(BaseModel):
    """Estado de um job de análise."""

    id: str
    status: Literal["downloading", "analyzing", "done", "error"]
    error: str | None = None
    report: Report | None = None


class CeilingOut(BaseModel):
    """Uma opção da lista de teto."""

    midi: int
    user: str
    standard: str


class CeilingsOut(BaseModel):
    """Opções da lista de teto e a escolha padrão."""

    options: list[CeilingOut]
    default_midi: int
