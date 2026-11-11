"""Segurança de conta: segredo da sessão, senhas, JWT e tokens de e-mail."""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.domain.errors import DomainError


def secret_key() -> str:
    """Lê `SECRET_KEY` do ambiente; sem ela o app não sobe."""
    key = os.environ.get("SECRET_KEY")
    if not key:
        raise DomainError(
            "Defina SECRET_KEY com um segredo longo e aleatório "
            '(por exemplo `python -c "import secrets; print(secrets.token_urlsafe(48))"`).'
        )
    return key


ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=30)


def hash_password(password: str) -> str:
    """Gera o hash bcrypt (com salt); o bcrypt só aceita até 72 bytes, validados no schema."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Confere a senha contra o hash; entrada que o bcrypt recusa conta como senha errada."""
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user_id: UUID) -> str:
    """Assina um JWT com o id do usuário (`sub`) e validade de `TOKEN_TTL`."""
    payload = {"sub": str(user_id), "exp": datetime.now(UTC) + TOKEN_TTL}
    return jwt.encode(payload, secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> UUID | None:
    """Devolve o id do usuário do token, ou `None` se estiver adulterado, expirado ou inválido."""
    try:
        payload = jwt.decode(token, secret_key(), algorithms=[ALGORITHM])
        return UUID(payload["sub"])
    except jwt.InvalidTokenError, KeyError, ValueError:
        return None


def new_token() -> str:
    """Token aleatório e imprevisível para os links por e-mail (URL-safe)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash sha256 do token: o banco só guarda isto, nunca o texto que foi enviado."""
    return hashlib.sha256(token.encode()).hexdigest()
