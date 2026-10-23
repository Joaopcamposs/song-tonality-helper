"""Limites por IP (pedidos de análise e senhas erradas), em memória, numa janela de 1 hora."""

import os
import time
from collections import defaultdict, deque

from fastapi import Request

WINDOW_SECONDS = 3600
_hits: defaultdict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    """IP do cliente: o endereço da conexão, ou "desconhecido" se ele não vier."""
    return request.client.host if request.client else "desconhecido"


def _sweep() -> None:
    """Descarta as chaves cujas marcas expiraram todas, para `_hits` não crescer sem fim."""
    for key in list(_hits):
        _recent(key)


def _recent(key: str) -> deque[float]:
    """Pedidos do IP dentro da janela; descarta os antigos."""
    hits = _hits[key]
    limit = time.monotonic() - WINDOW_SECONDS
    while hits and hits[0] <= limit:
        hits.popleft()
    if not hits:
        del _hits[key]
    return hits


def exceeded(key: str, limit: int | None = None) -> bool:
    """Diz se a chave já gastou `limit` registros da janela (padrão `MAX_REQUESTS_PER_HOUR`, 20)."""
    _sweep()
    if limit is None:
        limit = int(os.environ.get("MAX_REQUESTS_PER_HOUR", "20"))
    return len(_recent(key)) >= limit


def record(key: str) -> None:
    """Conta um novo pedido do IP."""
    _sweep()
    _hits[key].append(time.monotonic())


def reset() -> None:
    """Esquece todos os pedidos; usado nos testes."""
    _hits.clear()
