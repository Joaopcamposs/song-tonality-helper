"""Dependências compartilhadas dos routers: a sessão atual (usuário logado)."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.security import decode_token
from app.services import account, store
from app.services.store import User

COOKIE_NAME = "session"

Session = Annotated[AsyncSession, Depends(store.get_session)]


async def get_current_user(request: Request, session: Session) -> User:
    """Lê o cookie de sessão e devolve o usuário; sem cookie válido responde 401."""
    token = request.cookies.get(COOKIE_NAME)
    user_id = decode_token(token) if token else None
    user = await account.get_user(session, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar.")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
