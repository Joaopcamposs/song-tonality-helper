from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from app.domain import security
from app.domain.errors import DomainError
from app.domain.schemas import RegisterRequest


def test_secret_key_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(DomainError, match="SECRET_KEY"):
        security.secret_key()


def test_secret_key_read_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "abc")
    assert security.secret_key() == "abc"


def test_password_roundtrip():
    password_hash = security.hash_password("segredo123")
    assert security.verify_password("segredo123", password_hash)
    assert not security.verify_password("outra-senha", password_hash)
    assert not security.verify_password("x", "lixo-que-nao-e-hash")


def test_session_token_roundtrip_and_rejections(monkeypatch):
    user_id = uuid4()
    token = security.create_token(user_id)
    assert security.decode_token(token) == user_id
    assert security.decode_token(token[:-2] + "xx") is None
    assert security.decode_token("lixo") is None
    expired = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(UTC) - timedelta(seconds=1)},
        "segredo-de-teste-com-mais-de-32-bytes-ok",
        algorithm="HS256",
    )
    assert security.decode_token(expired) is None


def test_email_token_hash():
    token = security.new_token()
    assert security.hash_token(token) == security.hash_token(token)
    assert security.hash_token(token) != token
    assert security.new_token() != token


@pytest.mark.parametrize("password", ["a" * 7, "a" * 73, "é" * 37])
def test_register_rejects_bad_passwords(password):
    with pytest.raises(ValidationError):
        RegisterRequest(name="Ana", email="ana@x.com", password=password)


def test_register_accepts_72_bytes():
    RegisterRequest(name="Ana", email="ana@x.com", password="a" * 72)
