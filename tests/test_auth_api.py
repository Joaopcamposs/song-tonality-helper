import httpx
import pytest

from app.main import app
from app.services import account, ratelimit

SIGNUP = {"name": "Ana", "email": "ana@x.com", "password": "segredo123"}


@pytest.fixture
def outbox(monkeypatch) -> list[dict[str, str]]:
    sent: list[dict[str, str]] = []

    async def fake_send(to: str, subject: str, text: str, html: str | None = None) -> None:
        sent.append({"to": to, "text": text})

    monkeypatch.setattr(account, "send_email", fake_send)
    return sent


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_register_login_me_logout(client, outbox):
    created = await client.post("/api/auth/register", json=SIGNUP)
    assert created.status_code == 201
    assert created.json()["email_verified"] is False
    assert len(outbox) == 1  # e-mail de confirmação
    assert (await client.get("/api/auth/me")).status_code == 401

    login = await client.post(
        "/api/auth/login", json={"email": " ANA@x.com", "password": "segredo123"}
    )
    assert login.status_code == 200
    assert "session" in client.cookies
    assert (await client.get("/api/auth/me")).json()["name"] == "Ana"

    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_wrong_password_and_unknown_email_look_the_same(client, outbox):
    await client.post("/api/auth/register", json=SIGNUP)
    wrong = await client.post(
        "/api/auth/login", json={"email": "ana@x.com", "password": "errada-1"}
    )
    unknown = await client.post(
        "/api/auth/login", json={"email": "nao@x.com", "password": "segredo123"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_register_duplicate_and_bad_password(client, outbox):
    await client.post("/api/auth/register", json=SIGNUP)
    again = await client.post("/api/auth/register", json={**SIGNUP, "email": "ANA@x.com"})
    assert again.status_code == 409
    for password in ("a" * 73, "curta"):
        bad = await client.post("/api/auth/register", json={**SIGNUP, "password": password})
        assert bad.status_code == 422


async def test_tampered_cookie_is_rejected(client, outbox):
    await client.post("/api/auth/register", json=SIGNUP)
    await client.post("/api/auth/login", json={"email": "ana@x.com", "password": "segredo123"})
    client.cookies.set("session", client.cookies["session"][:-3] + "abc")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_reset_password_flow(client, outbox):
    await client.post("/api/auth/register", json=SIGNUP)
    assert (
        await client.post("/api/auth/forgot-password", json={"email": "nao@x.com"})
    ).status_code == 204
    assert len(outbox) == 1  # só a confirmação do cadastro
    await client.post("/api/auth/forgot-password", json={"email": "ana@x.com"})
    token = outbox[1]["text"].split("?redefinir=")[1].split()[0]
    reset = await client.post(
        "/api/auth/reset-password", json={"token": token, "password": "nova-senha-1"}
    )
    assert reset.status_code == 204
    again = await client.post(
        "/api/auth/reset-password", json={"token": token, "password": "outra-senha-2"}
    )
    assert again.status_code == 400
    login = await client.post(
        "/api/auth/login", json={"email": "ana@x.com", "password": "nova-senha-1"}
    )
    assert login.status_code == 200


async def test_verify_email(client, outbox):
    await client.post("/api/auth/register", json=SIGNUP)
    token = outbox[0]["text"].split("?verificar=")[1].split()[0]
    assert (await client.post("/api/auth/verify-email", json={"token": token})).status_code == 204
    await client.post("/api/auth/login", json={"email": "ana@x.com", "password": "segredo123"})
    assert (await client.get("/api/auth/me")).json()["email_verified"] is True
    bad = await client.post("/api/auth/verify-email", json={"token": "inventado"})
    assert bad.status_code == 400


async def test_login_rate_limit(client, outbox):
    await client.post("/api/auth/register", json=SIGNUP)
    ratelimit.reset()
    wrong = {"email": "ana@x.com", "password": "errada-123"}
    for _ in range(10):
        assert (await client.post("/api/auth/login", json=wrong)).status_code == 401
    assert (await client.post("/api/auth/login", json=wrong)).status_code == 429
