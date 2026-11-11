"""Casos de uso da conta: cadastro, login, confirmação de e-mail e redefinição de senha."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import uuid_utils.compat as uuid_utils
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import EmailAlreadyRegistered, InvalidAuthToken, InvalidCredentials
from app.domain.security import hash_password, hash_token, new_token, verify_password
from app.services.mail_templates import action_email
from app.services.mailer import send_email
from app.services.store import AuthToken, User

VERIFY = "verify"
RESET = "reset"
TOKEN_TTL = {VERIFY: timedelta(days=3), RESET: timedelta(hours=1)}
DEFAULT_APP_URL = "http://localhost:8007"


def now_utc() -> datetime:
    """Agora em UTC ingênuo, como as colunas de data do banco."""
    return datetime.now(UTC).replace(tzinfo=None)


def _app_url() -> str:
    """Endereço público do app, usado nos links dos e-mails."""
    return os.environ.get("APP_URL", DEFAULT_APP_URL).rstrip("/")


def normalize_email(email: str) -> str:
    """E-mail sem espaços nas pontas e em minúsculas, para a mesma conta valer em qualquer caixa."""
    return email.strip().lower()


async def register_user(session: AsyncSession, name: str, email: str, password: str) -> User:
    """Cria a conta; e-mail já cadastrado levanta `EmailAlreadyRegistered`."""
    email = normalize_email(email)
    if await _by_email(session, email) is not None:
        raise EmailAlreadyRegistered("Já existe uma conta com esse e-mail.")
    user = User(
        id=uuid_utils.uuid7(),
        name=name.strip(),
        email=email,
        password_hash=await asyncio.to_thread(hash_password, password),
        created_at=now_utc(),
        email_verified_at=None,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:  # dois cadastros simultâneos com o mesmo e-mail
        await session.rollback()
        raise EmailAlreadyRegistered("Já existe uma conta com esse e-mail.") from None
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Confere e-mail e senha; qualquer falha levanta o mesmo `InvalidCredentials`."""
    user = await _by_email(session, normalize_email(email))
    # Sem conta, confere contra um hash qualquer para o tempo não revelar se o e-mail existe.
    password_hash = user.password_hash if user else _DUMMY_HASH
    valid = await asyncio.to_thread(verify_password, password, password_hash)
    if user is None or not valid:
        raise InvalidCredentials("E-mail ou senha incorretos.")
    return user


async def get_user(session: AsyncSession, user_id: UUID) -> User | None:
    """Busca a conta pelo id (ou `None`)."""
    return await session.get(User, user_id)


async def send_verification(session: AsyncSession, user: User) -> None:
    """Manda o link de confirmação do e-mail; quem já confirmou não recebe nada."""
    if user.email_verified_at is not None:
        return
    raw = await _issue(session, user, VERIFY)
    text, html = action_email(
        user.name,
        "Confirme seu e-mail",
        "Falta só um passo: confirme que este e-mail é seu para recuperar a conta se precisar.",
        "Confirmar meu e-mail",
        f"{_app_url()}/?verificar={raw}",
        "Este link vale por 3 dias. Se você não criou uma conta no Tonalidade, ignore este e-mail.",
    )
    await send_email(user.email, "Confirme seu e-mail no Tonalidade", text, html)


async def verify_email(session: AsyncSession, raw_token: str) -> None:
    """Confirma o e-mail do dono do token; token inválido ou usado levanta `InvalidAuthToken`."""
    token = await _consume(session, raw_token, VERIFY)
    user = await session.get(User, token.user_id)
    if user is not None:
        user.email_verified_at = now_utc()
    await session.commit()


async def request_password_reset(session: AsyncSession, email: str) -> None:
    """Manda o link de redefinição; e-mail desconhecido passa em silêncio (não revela contas)."""
    user = await _by_email(session, normalize_email(email))
    if user is None:
        return
    raw = await _issue(session, user, RESET)
    text, html = action_email(
        user.name,
        "Redefina sua senha",
        "Recebemos um pedido para escolher uma senha nova. Se foi você, use o botão abaixo.",
        "Redefinir minha senha",
        f"{_app_url()}/?redefinir={raw}",
        "Este link vale por 1 hora. Se não foi você, ignore este e-mail: a senha continua a mesma.",
    )
    await send_email(user.email, "Redefinir sua senha no Tonalidade", text, html)


async def reset_password(session: AsyncSession, raw_token: str, password: str) -> None:
    """Troca a senha com o token do e-mail; token inválido, vencido ou usado levanta erro."""
    token = await _consume(session, raw_token, RESET)
    user = await session.get(User, token.user_id)
    if user is None:
        raise InvalidAuthToken("Este link é inválido ou venceu. Peça um novo.")
    user.password_hash = await asyncio.to_thread(hash_password, password)
    await session.commit()


async def _by_email(session: AsyncSession, email: str) -> User | None:
    """Busca a conta pelo e-mail já normalizado."""
    return await session.scalar(select(User).where(User.email == email))


async def _issue(session: AsyncSession, user: User, kind: str) -> str:
    """Cria um token novo (os pendentes do mesmo tipo deixam de valer) e devolve o texto do link."""
    raw = new_token()
    await session.execute(
        delete(AuthToken).where(
            AuthToken.user_id == user.id, AuthToken.kind == kind, AuthToken.used_at.is_(None)
        )
    )
    now = now_utc()
    session.add(
        AuthToken(
            id=uuid_utils.uuid7(),
            user_id=user.id,
            kind=kind,
            token_hash=hash_token(raw),
            expires_at=now + TOKEN_TTL[kind],
            used_at=None,
            created_at=now,
        )
    )
    await session.commit()
    return raw


async def _consume(session: AsyncSession, raw_token: str, kind: str) -> AuthToken:
    """Marca o token como usado e o devolve; inexistente, vencido ou usado levanta erro."""
    token = await session.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == hash_token(raw_token), AuthToken.kind == kind
        )
    )
    now = now_utc()
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise InvalidAuthToken("Este link é inválido ou venceu. Peça um novo.")
    token.used_at = now
    return token


# Hash de uma senha descartável, só para igualar o custo do login com e-mail inexistente.
_DUMMY_HASH = hash_password("senha-descartavel")
