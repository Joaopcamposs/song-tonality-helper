"""Segurança de conta: segredo da sessão, senhas, JWT e tokens de e-mail."""

import os

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
