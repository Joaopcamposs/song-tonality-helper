import asyncio
import os
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import pytest_asyncio
import soundfile as sf
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.services import migrate, ratelimit, store

# Segredo fixo só para os testes; a API exige `SECRET_KEY` ao subir.
os.environ.setdefault("SECRET_KEY", "segredo-de-teste-com-mais-de-32-bytes-ok")

SAMPLE_RATE = 22050
DEFAULT_TEST_URL = "postgresql+asyncpg://postgres:dev@localhost:5432/tonalidade_test"


@pytest.fixture
def make_wav(tmp_path: Path) -> Callable[[list[tuple[int | None, float]]], Path]:
    """Gera um wav mono ruidoso a partir de (nota MIDI ou None para silêncio, segundos)."""

    def build(notes: list[tuple[int | None, float]]) -> Path:
        rng = np.random.default_rng(0)
        parts = []
        for midi, seconds in notes:
            t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
            if midi is None:
                parts.append(np.zeros_like(t))
                continue
            freq = 440.0 * 2 ** ((midi - 69) / 12)
            wave = sum(np.sin(2 * np.pi * freq * h * t) / h for h in (1, 2, 3))
            # Ruído fixo faz a confiança variar por quadro, como numa gravação real.
            parts.append(wave + rng.normal(0, 0.3, t.size))
        audio = np.concatenate(parts)
        audio = 0.5 * audio / max(np.abs(audio).max(), 1e-9)
        path = tmp_path / "synthetic.wav"
        sf.write(path, audio, SAMPLE_RATE)
        return path

    return build


TEST_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Recria o schema do app e aplica as migrações, uma vez por sessão de testes."""

    async def drop_schema() -> None:
        cleaner = create_async_engine(TEST_URL)
        try:
            async with cleaner.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{store.SCHEMA}" CASCADE'))
        finally:
            await cleaner.dispose()

    try:
        asyncio.run(drop_schema())
    except OSError, DBAPIError:
        pytest.exit("Postgres de testes inacessível: rode `make db` (ou defina TEST_DATABASE_URL).")
    migrate.upgrade_head(TEST_URL)


@pytest_asyncio.fixture(autouse=True)
async def db(migrated_database: None):
    """Esvazia todas as tabelas do app antes de cada teste e aponta o store para o banco."""
    store.configure(TEST_URL)
    tables = ", ".join(
        f'"{store.SCHEMA}"."{table.name}"' for table in store.Base.metadata.sorted_tables
    )
    async with store.session() as session:
        await session.execute(text(f"TRUNCATE {tables}"))
        await session.commit()
    yield
    await store.dispose()


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Zera os contadores do limite de pedidos entre os testes."""
    ratelimit.reset()
