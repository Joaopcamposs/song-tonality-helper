import asyncio
from datetime import timedelta
from pathlib import Path

from sqlalchemy import update

from app import worker
from app.domain.errors import DownloadError
from app.domain.features import AudioFeatures
from app.services import jobs, store
from app.services.download import DownloadedAudio
from app.services.store import Job

VIDEO_ID = "dQw4w9WgXcQ"


def _fake_pipeline(monkeypatch, calls: list[str]) -> None:
    def download(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
        calls.append(video_id)
        return DownloadedAudio(dest_dir / "audio.wav", "Música", 100)

    features = AudioFeatures(
        top_midi=71, ranking=[(71, 150)], top_times=[1.0], chroma_profile=[0.1] * 12
    )
    monkeypatch.setattr(worker, "download_audio", download)
    monkeypatch.setattr(worker, "analyze_audio", lambda path: features)


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
    def failing(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
        raise DownloadError("Não consegui baixar o áudio deste vídeo.")

    monkeypatch.setattr(worker, "download_audio", failing)
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


async def test_job_stuck_by_db_failure_is_requeued_and_finishes(monkeypatch):
    calls: list[str] = []
    _fake_pipeline(monkeypatch, calls)
    await _enqueue()
    real_finish, real_fail = worker._finish, worker._fail
    failures = {"left": 1}

    async def flaky_finish(video_id: str) -> None:
        if failures["left"]:
            raise OSError("banco caiu")
        await real_finish(video_id)

    async def flaky_fail(video_id: str, message: str) -> None:
        if failures["left"]:
            failures["left"] -= 1
            raise OSError("banco caiu")
        await real_fail(video_id, message)

    monkeypatch.setattr(worker, "_finish", flaky_finish)
    monkeypatch.setattr(worker, "_fail", flaky_fail)
    busy, needs_recovery = await worker.run_once(False)
    assert (busy, needs_recovery) == (False, True)
    busy, needs_recovery = await worker.run_once(needs_recovery)
    assert (busy, needs_recovery) == (True, False)
    async with store.session() as session:
        assert await store.find(session, VIDEO_ID) is not None
        assert await jobs.get(session, VIDEO_ID) is None


async def _age_job(seconds: float) -> None:
    """Envelhece o `updated_at` do job, simulando um executor que sumiu."""
    async with store.session() as session:
        await session.execute(
            update(Job)
            .where(Job.video_id == VIDEO_ID)
            .values(updated_at=jobs.now() - timedelta(seconds=seconds))
        )
        await session.commit()


async def test_stale_downloading_job_is_claimed(monkeypatch):
    calls: list[str] = []
    _fake_pipeline(monkeypatch, calls)
    await _enqueue()
    async with store.session() as session:
        await jobs.claim(session)  # a API caiu no meio da extração
    await _age_job(jobs.STALE_SECONDS + 10)
    assert await worker.process_next() is True
    assert calls == [VIDEO_ID]
    async with store.session() as session:
        assert await store.find(session, VIDEO_ID) is not None


async def test_recent_downloading_job_is_not_claimed(monkeypatch):
    calls: list[str] = []
    _fake_pipeline(monkeypatch, calls)
    await _enqueue()
    async with store.session() as session:
        await jobs.claim(session)
    await _age_job(jobs.STALE_SECONDS - 60)
    assert await worker.process_next() is False
    assert calls == []
