"""Modelos Pydantic da API: pedido de análise, andamento, lista e relatório."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, EmailStr, Field


class NoteOut(BaseModel):
    """Uma nota com oitava (dó central = C4)."""

    midi: int
    name: str


class RankedNote(BaseModel):
    """Uma nota do ranking e quantos quadros ela ocupou."""

    note: NoteOut
    frames: int


class KeySectionOut(BaseModel):
    """Trecho da música num mesmo tom: início, tom, correlação e o tom depois de transpor."""

    start: float
    tonic: str
    mode: Literal["maior", "menor"]
    score: float
    new_key: str
    relative: str | None = None  # tom relativo quase tão provável (mesmas notas), ex.: "A menor"


class Report(BaseModel):
    """Relatório final da análise de uma música."""

    top_note: NoteOut
    ceiling: NoteOut
    ranking: list[RankedNote]
    top_times: list[float]
    sections: list[KeySectionOut]
    shift: int
    alternative_shift: int
    new_key: str  # novo tom do primeiro trecho
    scale_degree: str  # grau da nota mais aguda no tom do primeiro trecho
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


def _check_password(password: str) -> str:
    """Aceita senhas de 8 caracteres até 72 bytes (limite do bcrypt)."""
    if len(password) < 8:
        raise ValueError("A senha precisa ter pelo menos 8 caracteres.")
    if len(password.encode()) > 72:
        raise ValueError("A senha pode ter no máximo 72 bytes.")
    return password


Password = Annotated[str, AfterValidator(_check_password)]


class RegisterRequest(BaseModel):
    """Cadastro de uma conta nova."""

    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: Password


class LoginRequest(BaseModel):
    """Entrada com e-mail e senha."""

    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Pedido do link para redefinir a senha."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Nova senha, com o token recebido por e-mail."""

    token: str
    password: Password


class TokenRequest(BaseModel):
    """Token recebido por e-mail (confirmação de endereço)."""

    token: str


class UserRead(BaseModel):
    """A pessoa logada, sem dados sensíveis."""

    id: UUID
    name: str
    email: str
    email_verified: bool
