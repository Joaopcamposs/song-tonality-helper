"""Rotas de conta: cadastro, login, logout, usuário atual, e-mail e senha."""

import os

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.domain.errors import EmailAlreadyRegistered, InvalidAuthToken, InvalidCredentials
from app.domain.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
    UserRead,
)
from app.domain.security import TOKEN_TTL, create_token
from app.routers.deps import COOKIE_NAME, CurrentUserDep, Session
from app.services import account, ratelimit
from app.services.store import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Tentativas por hora e por IP (as senhas erradas contam no login; os demais, cada pedido).
AUTH_LIMIT = 10
TOO_MANY = "Muitas tentativas, tente de novo mais tarde."


def _read(user: User) -> UserRead:
    """Converte a conta para a resposta pública."""
    return UserRead(
        id=user.id,
        name=user.name,
        email=user.email,
        email_verified=user.email_verified_at is not None,
    )


def _check_limit(request: Request, bucket: str) -> str:
    """Barra o IP que passou do limite do grupo e devolve a chave dele."""
    key = f"{bucket}:{ratelimit.client_ip(request)}"
    if ratelimit.exceeded(key, AUTH_LIMIT):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)
    return key


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra uma conta",
    description=(
        "Cria a conta (nome, e-mail e senha de 8 a 72 bytes) e manda o link de confirmação do "
        "e-mail. 409 se o e-mail já existe; 429 se o IP passou de 10 cadastros por hora."
    ),
)
async def register(body: RegisterRequest, request: Request, session: Session) -> UserRead:
    """Cadastro público; o usuário já pode usar o app sem confirmar o e-mail."""
    key = _check_limit(request, "register")
    try:
        user = await account.register_user(session, body.name, body.email, body.password)
    except EmailAlreadyRegistered as error:
        raise HTTPException(status.HTTP_409_CONFLICT, error.message) from error
    ratelimit.record(key)
    await account.send_verification(session, user)
    return _read(user)


@router.post(
    "/login",
    summary="Entra no app",
    description=(
        "Confere e-mail e senha e grava a sessão (30 dias) em cookie. 401 genérico para "
        "qualquer falha; 429 depois de 10 tentativas erradas por hora no mesmo IP."
    ),
)
async def login(
    body: LoginRequest, request: Request, response: Response, session: Session
) -> UserRead:
    """Autentica e grava o JWT no cookie de sessão."""
    key = _check_limit(request, "login")
    try:
        user = await account.authenticate(session, body.email, body.password)
    except InvalidCredentials as error:
        ratelimit.record(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, error.message) from error
    response.set_cookie(
        COOKIE_NAME,
        create_token(user.id),
        max_age=int(TOKEN_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=os.environ.get("COOKIE_SECURE", "").lower() in {"1", "true"},
    )
    return _read(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sai do app",
    description="Apaga o cookie de sessão.",
)
async def logout(response: Response) -> None:
    """Remove o cookie de sessão."""
    response.delete_cookie(COOKIE_NAME)


@router.get(
    "/me",
    summary="Usuário atual",
    description="Devolve a pessoa da sessão; 401 se não houver sessão válida.",
)
async def me(user: CurrentUserDep) -> UserRead:
    """Quem está logado."""
    return _read(user)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Pede o link para redefinir a senha",
    description=(
        "Manda por e-mail um link que vale 1 hora. Responde sempre 204, exista a conta ou "
        "não, para não revelar quem tem cadastro."
    ),
)
async def forgot_password(body: ForgotPasswordRequest, request: Request, session: Session) -> None:
    """Pede o e-mail de redefinição."""
    ratelimit.record(_check_limit(request, "mail"))
    await account.request_password_reset(session, body.email)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Define a senha nova",
    description="Usa o token do e-mail e troca a senha; 400 se o link for inválido ou venceu.",
)
async def reset_password(body: ResetPasswordRequest, request: Request, session: Session) -> None:
    """Troca a senha com o token recebido."""
    ratelimit.record(_check_limit(request, "mail"))
    try:
        await account.reset_password(session, body.token, body.password)
    except InvalidAuthToken as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error.message) from error


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirma o e-mail",
    description="Usa o token do e-mail de confirmação; 400 se o link for inválido ou venceu.",
)
async def verify_email(body: TokenRequest, request: Request, session: Session) -> None:
    """Confirma o e-mail com o token recebido."""
    ratelimit.record(_check_limit(request, "mail"))
    try:
        await account.verify_email(session, body.token)
    except InvalidAuthToken as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, error.message) from error
