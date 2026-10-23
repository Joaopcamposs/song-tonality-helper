"""Id do vídeo a partir do link do YouTube."""

import re
from urllib.parse import parse_qs, urlparse

from app.domain.errors import InvalidUrlError

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def parse_video_id(url: str) -> str:
    """Extrai o id do vídeo de um link do YouTube ou levanta `InvalidUrlError`."""
    parsed = urlparse(url.strip())
    if parsed.scheme in {"http", "https"} and parsed.hostname in _ALLOWED_HOSTS:
        segments = [part for part in parsed.path.split("/") if part]
        if parsed.hostname == "youtu.be":
            candidate = segments[0] if segments else ""
        elif segments[:1] in (["shorts"], ["live"], ["embed"]) and len(segments) > 1:
            candidate = segments[1]
        elif segments == ["watch"]:
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        else:
            candidate = ""
        if _VIDEO_ID.fullmatch(candidate):
            return candidate
        first = segments[0] if segments else ""
        if first.startswith("@") or first in {"channel", "c", "user"}:
            raise InvalidUrlError("Esse link é de um canal; informe o link de um vídeo.")
        if first == "playlist":
            raise InvalidUrlError("Esse link é de uma playlist; informe o link de um vídeo.")
    raise InvalidUrlError("Informe um link de vídeo do YouTube.")
