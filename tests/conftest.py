import os
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import pytest_asyncio
import soundfile as sf
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.services import ratelimit, store

SAMPLE_RATE = 22050


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


@pytest_asyncio.fixture(autouse=True)
async def db(tmp_path: Path):
    """Banco novo para cada teste: SQLite temporário ou o Postgres de `TEST_DATABASE_URL`."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url is None:
        store.configure(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    else:
        # O Postgres persiste entre testes: apaga o schema do app antes de cada um.
        cleaner = create_async_engine(url)
        async with cleaner.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{store.SCHEMA}" CASCADE'))
        await cleaner.dispose()
        store.configure(url)
    await store.create_tables()
    yield
    await store.dispose()


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Zera os contadores do limite de pedidos entre os testes."""
    ratelimit.reset()
