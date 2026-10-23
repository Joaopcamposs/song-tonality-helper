from types import SimpleNamespace

from app.services import ratelimit


def _request(header: str | None, host: str = "172.18.0.2"):
    headers = {"cf-connecting-ip": header} if header else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_client_ip_prefers_cloudflare_header():
    assert ratelimit.client_ip(_request("203.0.113.7")) == "203.0.113.7"  # type: ignore[arg-type]
    assert ratelimit.client_ip(_request(None)) == "172.18.0.2"  # type: ignore[arg-type]


def test_expired_keys_are_dropped_on_next_call(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: now[0])
    ratelimit.record("antigo")
    now[0] += ratelimit.WINDOW_SECONDS + 1
    ratelimit.record("novo")
    assert list(ratelimit._hits) == ["novo"]
    now[0] += ratelimit.WINDOW_SECONDS + 1
    assert ratelimit.exceeded("outro") is False
    assert not ratelimit._hits
