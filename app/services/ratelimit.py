"""Limite de novos pedidos de análise por IP, em memória, numa janela de 1 hora."""

import os
import time
from collections import defaultdict, deque

WINDOW_SECONDS = 3600
_hits: defaultdict[str, deque[float]] = defaultdict(deque)


def _recent(key: str) -> deque[float]:
    """Pedidos do IP dentro da janela; descarta os antigos."""
    hits = _hits[key]
    limit = time.monotonic() - WINDOW_SECONDS
    while hits and hits[0] <= limit:
        hits.popleft()
    if not hits:
        del _hits[key]
    return hits


def exceeded(key: str) -> bool:
    """Diz se o IP já gastou os `MAX_REQUESTS_PER_HOUR` pedidos (padrão 20) da janela."""
    return len(_recent(key)) >= int(os.environ.get("MAX_REQUESTS_PER_HOUR", "20"))


def record(key: str) -> None:
    """Conta um novo pedido do IP."""
    _hits[key].append(time.monotonic())


def reset() -> None:
    """Esquece todos os pedidos; usado nos testes."""
    _hits.clear()
