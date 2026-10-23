import logging
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from app import worker
from app.domain.errors import DownloadError, NoMelodyError
from app.domain.features import AudioFeatures
from app.main import app
from app.services import jobs, store
from app.services.download import DownloadedAudio

VIDEO_ID = "dQw4w9WgXcQ"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
PROXY = "http://usuario:segredo123@proxy.exemplo:8080"


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def pipeline(monkeypatch):
    """Duplo do download e da análise; guarda o proxy recebido em cada chamada."""
    calls: list[str | None] = []
    behavior: dict[str, Exception | None] = {"download": None, "analyze": None}

    def download(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
        calls.append(proxy)
        if (error := behavior["download"]) is not None and proxy is not None:
            raise error
        return DownloadedAudio(dest_dir / "audio.wav", "Música", 100)

    def analyze(path: Path) -> AudioFeatures:
        if (error := behavior["analyze"]) is not None:
            raise error
        return AudioFeatures(
            top_midi=71, ranking=[(71, 150)], top_times=[1.0], chroma_profile=[0.1] * 12
        )

    monkeypatch.setattr(worker, "download_audio", download)
    monkeypatch.setattr(worker, "analyze_audio", analyze)
    return calls, behavior


async def _progress():
    async with store.session() as session:
        return await jobs.get(session, VIDEO_ID)


async def _saved() -> bool:
    async with store.session() as session:
        return await store.find(session, VIDEO_ID) is not None


async def test_proxy_off_leaves_job_pending(client, pipeline, monkeypatch):
    monkeypatch.delenv("DOWNLOAD_PROXY_URL", raising=False)
    calls, _ = pipeline
    await client.post("/api/analyses", json={"url": URL})
    assert calls == []
    assert await _progress() == jobs.Progress("pending")


async def test_proxy_on_finishes_without_worker(client, pipeline, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_PROXY_URL", PROXY)
    calls, _ = pipeline
    await client.post("/api/analyses", json={"url": URL})
    assert calls == [PROXY]
    assert await _saved()
    assert await _progress() is None


async def test_download_failure_returns_to_pending_and_worker_finishes(
    client, pipeline, monkeypatch
):
    monkeypatch.setenv("DOWNLOAD_PROXY_URL", PROXY)
    calls, behavior = pipeline
    behavior["download"] = DownloadError("Não consegui baixar o áudio deste vídeo.")
    await client.post("/api/analyses", json={"url": URL})
    assert await _progress() == jobs.Progress("pending")
    assert await worker.process_next() is True
    assert calls == [PROXY, None]
    assert await _saved()


async def test_analysis_error_is_not_retried_by_worker(client, pipeline, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_PROXY_URL", PROXY)
    _, behavior = pipeline
    behavior["analyze"] = NoMelodyError("Não encontrei uma melodia detectável.")
    await client.post("/api/analyses", json={"url": URL})
    assert await _progress() == jobs.Progress("error", "Não encontrei uma melodia detectável.")


async def test_unexpected_error_returns_to_pending(client, pipeline, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_PROXY_URL", PROXY)
    _, behavior = pipeline
    behavior["download"] = RuntimeError("quebrou")
    await client.post("/api/analyses", json={"url": URL})
    assert await _progress() == jobs.Progress("pending")


async def test_job_claimed_by_worker_is_not_touched(pipeline, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_PROXY_URL", PROXY)
    calls, _ = pipeline
    async with store.session() as session:
        await jobs.start(session, VIDEO_ID)
    async with store.session() as session:
        assert await jobs.claim(session) == VIDEO_ID  # o worker pegou primeiro
    await worker.try_with_proxy(VIDEO_ID)
    assert calls == []
    assert await _progress() == jobs.Progress("downloading")


async def test_proxy_url_never_reaches_logs(client, pipeline, monkeypatch, caplog):
    monkeypatch.setenv("DOWNLOAD_PROXY_URL", PROXY)
    _, behavior = pipeline
    behavior["download"] = RuntimeError(f"falha ao conectar em {PROXY}")
    with caplog.at_level(logging.DEBUG):
        await client.post("/api/analyses", json={"url": URL})
    assert caplog.records
    assert "segredo123" not in caplog.text
    assert PROXY not in caplog.text
