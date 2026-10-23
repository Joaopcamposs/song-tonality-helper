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
    client = f"senha:{ratelimit.client_ip(request)}"
    if ratelimit.exceeded(client, MAX_FAILURES_PER_HOUR):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Tentativas demais, tente de novo mais tarde."
        )
    # Cabeçalhos HTTP são latin-1: valores fora disso viram "?" em vez de levantar exceção.
    sent = request.headers.get(HEADER)
    given = (sent or "").encode("latin-1", errors="replace")
    if not secrets.compare_digest(given, expected.encode("latin-1", errors="replace")):
        if sent is not None:  # sem cabeçalho é só a página abrindo; palpite errado é que conta
            ratelimit.record(client)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Palavra secreta ausente ou incorreta.")
