import pytest

from app.domain import security
from app.domain.errors import DomainError


def test_secret_key_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(DomainError, match="SECRET_KEY"):
        security.secret_key()


def test_secret_key_read_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "abc")
    assert security.secret_key() == "abc"
