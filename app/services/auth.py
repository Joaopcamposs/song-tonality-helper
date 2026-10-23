"""Proteção opcional por palavra secreta (`APP_PASSPHRASE`), sem login nem usuários."""

import os
import secrets

from fastapi import HTTPException, Request, status

from app.services import ratelimit

HEADER = "X-App-Passphrase"
MAX_FAILURES_PER_HOUR = 10


def require_passphrase(request: Request) -> None:
    """Dependência das rotas `/api`: exige o cabeçalho se `APP_PASSPHRASE` estiver definida."""
    expected = os.environ.get("APP_PASSPHRASE", "")
    if not expected:  # vazia ou ausente: proteção desligada
        return
    client = f"senha:{request.client.host if request.client else 'desconhecido'}"
    if ratelimit.exceeded(client, MAX_FAILURES_PER_HOUR):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Tentativas demais, tente de novo mais tarde."
        )
    given = request.headers.get(HEADER, "")
    if not secrets.compare_digest(given.encode(), expected.encode()):
        ratelimit.record(client)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Palavra secreta ausente ou incorreta.")
