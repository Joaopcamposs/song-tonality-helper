"""Rotas das preferências da pessoa logada (tom teto)."""

from fastapi import APIRouter

from app.domain.schemas import SettingsIn, SettingsOut
from app.routers.deps import CurrentUserDep, Session
from app.services import store

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get(
    "/settings",
    summary="Lê as minhas preferências",
    description="Devolve o tom teto salvo (ou o padrão, se ainda não foi escolhido).",
)
async def get_settings(session: Session, user: CurrentUserDep) -> SettingsOut:
    """Preferências da pessoa."""
    return SettingsOut(ceiling_midi=await store.get_ceiling(session, user.id))


@router.put(
    "/settings",
    summary="Salva as minhas preferências",
    description="Guarda o tom teto (`ceiling_midi` de 48 a 72); 422 fora dessa faixa.",
)
async def put_settings(body: SettingsIn, session: Session, user: CurrentUserDep) -> SettingsOut:
    """Troca o tom teto da pessoa."""
    await store.set_ceiling(session, user.id, body.ceiling_midi)
    return SettingsOut(ceiling_midi=body.ceiling_midi)
