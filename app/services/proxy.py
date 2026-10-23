"""Configuração do proxy residencial (formato Oxylabs) usado no download do yt-dlp."""

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote

DEFAULT_PROXY_HOST = "pr.oxylabs.io:7777"


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    """Credenciais e opções do proxy; sem usuário e senha o proxy fica desligado."""

    username: str
    password: str
    host: str = DEFAULT_PROXY_HOST
    country: str | None = None
    session_minutes: int | None = None  # None: IP novo a cada request

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> ProxyConfig | None:
        """Lê as variáveis `PROXY_*`; devolve None se faltar usuário ou senha."""
        username, password = env.get("PROXY_USERNAME"), env.get("PROXY_PASSWORD")
        if not username or not password:
            return None
        minutes = env.get("PROXY_SESSION_MINUTES")
        return cls(
            username=username,
            password=password,
            host=env.get("PROXY_HOST") or DEFAULT_PROXY_HOST,
            country=env.get("PROXY_COUNTRY") or None,
            session_minutes=int(minutes) if minutes else None,
        )

    def url(self) -> str:
        """URL do proxy. Com sessão, o IP fica fixo por `session_minutes` (sticky)."""
        user = f"customer-{self.username}"
        if self.country:
            user += f"-cc-{self.country}"
        if self.session_minutes:
            user += f"-sessid-{secrets.token_hex(5)}-sesstime-{self.session_minutes}"
        return f"http://{user}:{quote(self.password, safe='')}@{self.host}"
