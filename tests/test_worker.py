import asyncio
from pathlib import Path

from app import worker
from app.domain.errors import DownloadError
from app.domain.pitch import AudioFeatures
from app.services import jobs, store
from app.services.youtube import DownloadedAudio

VIDEO_ID = "dQw4w9WgXcQ"


def _fake_pipeline(monkeypatch, calls: list[str]) -> None:
    def download(video_id: str, dest_dir: Path) -> DownloadedAudio:
        calls.append(video_id)
        return DownloadedAudio(dest_dir / "audio.wav", "Música", 100)

    features = AudioFeatures(
        top_midi=71, ranking=[(71, 150)], top_times=[1.0], chroma_profile=[0.1] * 12
    )
    monkeypatch.setattr(jobs, "download_audio", download)
    monkeypatch.setattr(jobs, "analyze_audio", lambda path: features)


async def _enqueue(video_id: str = VIDEO_ID) -> None:
    async with store.session() as session:
        await jobs.start(session, video_id)


async def test_empty_queue_returns_false():
    assert await worker.process_next() is False


async def test_pending_job_is_processed_and_saved(monkeypatch):
    calls: list[str] = []
    _fake_pipeline(monkeypatch, calls)
    await _enqueue()
    assert await worker.process_next() is True
    assert await worker.process_next() is False
    async with store.session() as session:
        assert await store.find(session, VIDEO_ID) is not None
        assert await jobs.get(session, VIDEO_ID) is None
    assert calls == [VIDEO_ID]


async def test_two_workers_run_a_job_only_once(monkeypatch):
    calls: list[str] = []
    _fake_pipeline(monkeypatch, calls)
    await _enqueue()
    results = await asyncio.gather(worker.process_next(), worker.process_next())
    assert sorted(results) == [False, True]
    assert calls == [VIDEO_ID]


async def test_pipeline_failure_becomes_error_job(monkeypatch):
    def failing(video_id: str, dest_dir: Path) -> DownloadedAudio:
        raise DownloadError("Não consegui baixar o áudio deste vídeo.")

    monkeypatch.setattr(jobs, "download_audio", failing)
    await _enqueue()
    assert await worker.process_next() is True
    async with store.session() as session:
        progress = await jobs.get(session, VIDEO_ID)
    assert progress == jobs.Progress("error", "Não consegui baixar o áudio deste vídeo.")


async def test_orphans_are_requeued_when_worker_starts(monkeypatch):
    calls: list[str] = []
    _fake_pipeline(monkeypatch, calls)
    await _enqueue()
    async with store.session() as session:
        await jobs.claim(session)  # o worker anterior caiu com o job em andamento
    await worker.recover_orphans()
    assert await worker.process_next() is True
    assert calls == [VIDEO_ID]
