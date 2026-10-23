import httpx
import pytest_asyncio
from httpx import ASGITransport

from app.main import app

HEADER = "X-App-Passphrase"


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_disabled_lets_everything_pass(client, monkeypatch):
    monkeypatch.delenv("APP_PASSPHRASE", raising=False)
    assert (await client.get("/api/ceilings")).status_code == 200
    monkeypatch.setenv("APP_PASSPHRASE", "")
    assert (await client.get("/api/ceilings")).status_code == 200


async def test_enabled_requires_correct_header(client, monkeypatch):
    monkeypatch.setenv("APP_PASSPHRASE", "segredo")
    assert (await client.get("/api/ceilings")).status_code == 401
    assert (await client.get("/api/ceilings", headers={HEADER: "errada"})).status_code == 401
    assert (await client.get("/api/ceilings", headers={HEADER: "segredo"})).status_code == 200
    assert (await client.get("/api/analyses", headers={HEADER: "segredo"})).status_code == 200
    assert (await client.get("/api/analyses")).status_code == 401


async def test_health_and_frontend_stay_open(client, monkeypatch):
    monkeypatch.setenv("APP_PASSPHRASE", "segredo")
    assert (await client.get("/api/health")).status_code == 200
    assert (await client.get("/")).status_code == 200


async def test_too_many_failures_block_with_429(client, monkeypatch):
    monkeypatch.setenv("APP_PASSPHRASE", "segredo")
    for _ in range(10):
        assert (await client.get("/api/ceilings", headers={HEADER: "x"})).status_code == 401
    assert (await client.get("/api/ceilings", headers={HEADER: "x"})).status_code == 429
    assert (await client.get("/api/ceilings", headers={HEADER: "segredo"})).status_code == 429


async def test_invalid_header_encoding_is_401_not_500(client, monkeypatch):
    monkeypatch.setenv("APP_PASSPHRASE", "segredo")
    response = await client.get("/api/ceilings", headers={HEADER.encode(): "açaí é√".encode()})
    assert response.status_code == 401


async def test_failures_are_counted_per_cloudflare_ip(client, monkeypatch):
    monkeypatch.setenv("APP_PASSPHRASE", "segredo")
    for _ in range(10):
        await client.get("/api/ceilings", headers={HEADER: "x", "CF-Connecting-IP": "1.1.1.1"})
    first = {HEADER: "x", "CF-Connecting-IP": "1.1.1.1"}
    blocked = await client.get("/api/ceilings", headers=first)
    other = await client.get("/api/ceilings", headers={**first, "CF-Connecting-IP": "2.2.2.2"})
    assert (blocked.status_code, other.status_code) == (429, 401)
