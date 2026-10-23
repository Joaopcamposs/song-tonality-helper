import asyncio
import time
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from app import worker
from app.domain.features import AudioFeatures
from app.main import app
from app.services import jobs, store
from app.services.download import DownloadedAudio

VIDEO_ID = "dQw4w9WgXcQ"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def pipeline(monkeypatch):
    """Duplo do download e da análise; o download dorme `delay["first"]` s só na 1ª chamada."""
    monkeypatch.delenv("PROXY_USERNAME", raising=False)
    monkeypatch.delenv("PROXY_PASSWORD", raising=False)
    calls: list[str] = []
    delay = {"first": 0.0}

    def download(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
        calls.append(video_id)
        if len(calls) == 1:
            time.sleep(delay["first"])
        return DownloadedAudio(dest_dir / "audio.wav", "Música", 100)

    features = AudioFeatures(
        top_midi=71, ranking=[(71, 150)], top_times=[1.0], chroma_profile=[0.1] * 12
    )
    monkeypatch.setattr(worker, "download_audio", download)
    monkeypatch.setattr(worker, "analyze_audio", lambda path: features)
    return calls, delay


async def _progress():
    async with store.session() as session:
        return await jobs.get(session, VIDEO_ID)


async def _saved() -> bool:
    async with store.session() as session:
        return await store.find(session, VIDEO_ID) is not None


async def test_default_only_enqueues(client, pipeline):
    calls, _ = pipeline
    response = await client.post("/api/analyses", json={"url": URL})
    assert response.status_code == 202
    assert calls == []
    assert await _progress() == jobs.Progress("pending")


async def test_extract_now_finishes_without_worker(client, pipeline):
    calls, _ = pipeline
    response = await client.post("/api/analyses", json={"url": URL, "extract_now": True})
    assert response.status_code == 202
    assert calls == [VIDEO_ID]
    assert await _saved()
    assert await _progress() is None


async def test_slow_download_returns_to_pending_and_worker_finishes(client, pipeline, monkeypatch):
    calls, delay = pipeline
    monkeypatch.setattr(worker, "EXTRACT_TIMEOUT_SECONDS", 0.2)
    delay["first"] = 0.6
    await client.post("/api/analyses", json={"url": URL, "extract_now": True})
    assert await _progress() == jobs.Progress("pending")
    await asyncio.sleep(0.8)  # a thread tardia termina, mas o resultado dela é descartado
    assert not await _saved()
    assert await _progress() == jobs.Progress("pending")
    assert await worker.process_next() is True
    assert await _saved()
    assert calls == [VIDEO_ID, VIDEO_ID]
