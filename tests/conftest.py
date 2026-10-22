from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
import pytest_asyncio
import soundfile as sf

from app.services import store

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
    """Banco SQLite novo em arquivo temporário para cada teste."""
    store.configure(tmp_path / "test.db")
    await store.create_tables()
    yield
    await store.dispose()
