from datetime import timedelta

import pytest
from sqlalchemy import update

from app.domain.errors import EmailAlreadyRegistered, InvalidAuthToken, InvalidCredentials
from app.services import account, store


@pytest.fixture
def outbox(monkeypatch) -> list[dict[str, str]]:
    """Troca o envio de e-mail por uma lista em memória."""
    sent: list[dict[str, str]] = []

    async def fake_send(to: str, subject: str, text: str, html: str | None = None) -> None:
        sent.append({"to": to, "subject": subject, "text": text})

    monkeypatch.setattr(account, "send_email", fake_send)
    return sent


def link_token(mail: dict[str, str], param: str) -> str:
    return mail["text"].split(f"?{param}=")[1].split()[0]


async def test_register_normalizes_email_and_rejects_duplicates():
    async with store.session() as session:
        user = await account.register_user(session, "Ana", "  Ana@X.COM ", "segredo123")
        assert user.email == "ana@x.com"
        with pytest.raises(EmailAlreadyRegistered):
            await account.register_user(session, "Outra", "ANA@x.com", "segredo123")


async def test_authenticate_errors_are_generic():
    async with store.session() as session:
        await account.register_user(session, "Ana", "ana@x.com", "segredo123")
        assert (await account.authenticate(session, " ANA@x.com", "segredo123")).name == "Ana"
        with pytest.raises(InvalidCredentials) as wrong_password:
            await account.authenticate(session, "ana@x.com", "errada-123")
        with pytest.raises(InvalidCredentials) as unknown:
            await account.authenticate(session, "nao@existe.com", "segredo123")
        assert wrong_password.value.message == unknown.value.message


async def test_verify_email_flow(outbox):
    async with store.session() as session:
        user = await account.register_user(session, "Ana", "ana@x.com", "segredo123")
        await account.send_verification(session, user)
        raw = link_token(outbox[0], "verificar")
        await account.verify_email(session, raw)
        assert (await account.get_user(session, user.id)).email_verified_at is not None
        with pytest.raises(InvalidAuthToken):  # uso único
            await account.verify_email(session, raw)
        with pytest.raises(InvalidAuthToken):  # inventado
            await account.verify_email(session, "inventado")
        await account.send_verification(session, user)  # já confirmado: não envia
        assert len(outbox) == 1


async def test_expired_token_is_rejected(outbox):
    async with store.session() as session:
        user = await account.register_user(session, "Ana", "ana@x.com", "segredo123")
        await account.send_verification(session, user)
        await session.execute(
            update(store.AuthToken).values(expires_at=account.now_utc() - timedelta(seconds=1))
        )
        await session.commit()
        with pytest.raises(InvalidAuthToken):
            await account.verify_email(session, link_token(outbox[0], "verificar"))


async def test_reset_password_flow(outbox):
    async with store.session() as session:
        await account.register_user(session, "Ana", "ana@x.com", "segredo123")
        await account.request_password_reset(session, "Ana@x.com")
        raw = link_token(outbox[0], "redefinir")
        await account.reset_password(session, raw, "nova-senha-456")
        with pytest.raises(InvalidCredentials):
            await account.authenticate(session, "ana@x.com", "segredo123")
        await account.authenticate(session, "ana@x.com", "nova-senha-456")
        with pytest.raises(InvalidAuthToken):
            await account.reset_password(session, raw, "outra-senha-789")


async def test_reset_for_unknown_email_is_silent(outbox):
    async with store.session() as session:
        await account.request_password_reset(session, "nao@existe.com")
    assert outbox == []


async def test_new_token_invalidates_pending_one(outbox):
    async with store.session() as session:
        await account.register_user(session, "Ana", "ana@x.com", "segredo123")
        await account.request_password_reset(session, "ana@x.com")
        await account.request_password_reset(session, "ana@x.com")
        with pytest.raises(InvalidAuthToken):
            await account.reset_password(session, link_token(outbox[0], "redefinir"), "nova-123456")
        await account.reset_password(session, link_token(outbox[1], "redefinir"), "nova-123456")
