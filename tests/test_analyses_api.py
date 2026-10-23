import asyncio
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import func, select

from app import worker
from app.domain.errors import DomainError, DownloadError, NoMelodyError
from app.domain.features import ALGO_VERSION, AudioFeatures
from app.main import app
from app.services import jobs, store
from app.services.download import DownloadedAudio

VIDEO_ID = "dQw4w9WgXcQ"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
downloads: list[Path] = []


def _features() -> AudioFeatures:
    profile = [0.05] * 12
    for pc, weight in {7: 1.0, 11: 0.8, 2: 0.9, 9: 0.4, 0: 0.5, 4: 0.5, 6: 0.3}.items():
        profile[pc] = weight
    return AudioFeatures(top_midi=71, ranking=[(71, 150)], top_times=[12.3], chroma_profile=profile)


@pytest.fixture(autouse=True)
def fake_pipeline(monkeypatch):
    downloads.clear()

    def fake_download(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
        downloads.append(dest_dir)
        path = dest_dir / "audio.wav"
        path.write_bytes(b"RIFF")
        return DownloadedAudio(path, "Dois Passarinhos", 120)

    monkeypatch.setattr(worker, "download_audio", fake_download)
    monkeypatch.setattr(worker, "analyze_audio", lambda path: _features())


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _post(client: httpx.AsyncClient, url: str = URL) -> httpx.Response:
    return await client.post("/api/analyses", json={"url": url})


async def _analyze(client: httpx.AsyncClient, url: str = URL) -> httpx.Response:
    """Pede a análise e deixa o worker processar a fila, como no uso real."""
    response = await _post(client, url)
    while await worker.process_next():
        pass
    return response


async def test_new_video_is_202_then_done_with_report(client):
    response = await _analyze(client)
    assert response.status_code == 202
    assert response.json()["already_analyzed"] is False
    assert response.json()["video_id"] == VIDEO_ID
    body = (await client.get(f"/api/analyses/{VIDEO_ID}")).json()
    assert body["status"] == "done"
    assert body["title"] == "Dois Passarinhos"
    assert body["report"]["new_key"] == "D maior"
    assert not downloads[0].exists()


@pytest.mark.parametrize(
    "other",
    ["https://youtu.be/dQw4w9WgXcQ", f"https://music.youtube.com/watch?v={VIDEO_ID}&list=RDAMVM"],
)
async def test_same_video_other_link_is_200_and_not_downloaded_again(client, other):
    await _analyze(client)
    response = await _analyze(client, other)
    assert response.status_code == 200
    assert response.json()["already_analyzed"] is True
    assert response.json()["analyzed_at"] is not None
    assert len(downloads) == 1


async def test_get_other_ceiling_rebuilds_report_without_download(client):
    await _analyze(client)
    default = (await client.get(f"/api/analyses/{VIDEO_ID}")).json()["report"]
    other = (await client.get(f"/api/analyses/{VIDEO_ID}?ceiling_midi=60")).json()["report"]
    assert other["ceiling"]["midi"] == 60
    assert other["shift"] != default["shift"]
    assert len(downloads) == 1


@pytest.mark.parametrize(
    "url", ["https://evil.com/x", "https://www.youtube.com/playlist?list=PL123"]
)
async def test_invalid_urls_are_422_and_nothing_started(client, url):
    assert (await _analyze(client, url)).status_code == 422
    async with store.session() as session:
        assert await session.scalar(select(func.count()).select_from(store.Job)) == 0


@pytest.mark.parametrize("ceiling", [47, 73])
async def test_get_ceiling_out_of_range_is_422(client, ceiling):
    response = await client.get(f"/api/analyses/{VIDEO_ID}?ceiling_midi={ceiling}")
    assert response.status_code == 422


@pytest.mark.parametrize("video_id", ["nao-existe", "a%20b"])
async def test_unknown_or_malformed_video_id_is_404(client, video_id):
    assert (await client.get(f"/api/analyses/{video_id}")).status_code == 404


async def test_download_failure_is_error_not_saved_and_retry_works(client, monkeypatch):
    def failing(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
        raise DownloadError("Não consegui baixar o áudio deste vídeo.")

    ok = worker.download_audio
    monkeypatch.setattr(worker, "download_audio", failing)
    await _analyze(client)
    body = (await client.get(f"/api/analyses/{VIDEO_ID}")).json()
    assert body["status"] == "error"
    assert body["error"] == "Não consegui baixar o áudio deste vídeo."
    assert body["report"] is None
    assert (await client.get("/api/analyses")).json() == []

    monkeypatch.setattr(worker, "download_audio", ok)
    assert (await _analyze(client)).status_code == 202
    assert (await client.get(f"/api/analyses/{VIDEO_ID}")).json()["status"] == "done"


async def test_no_melody_error_is_reported(client, monkeypatch):
    def silent(path: Path) -> AudioFeatures:
        raise NoMelodyError("Não encontrei uma melodia detectável neste áudio.")

    monkeypatch.setattr(worker, "analyze_audio", silent)
    await _analyze(client)
    body = (await client.get(f"/api/analyses/{VIDEO_ID}")).json()
    assert body["status"] == "error"
    assert "melodia" in body["error"]


async def test_unexpected_failure_does_not_leak_details(client, monkeypatch):
    def broken(path: Path) -> AudioFeatures:
        raise RuntimeError("segredo interno")

    monkeypatch.setattr(worker, "analyze_audio", broken)
    await _analyze(client)
    body = (await client.get(f"/api/analyses/{VIDEO_ID}")).json()
    assert body["status"] == "error"
    assert "segredo interno" not in body["error"]


async def test_stale_algo_version_is_reanalyzed(client):
    await _analyze(client)
    async with store.session() as session:
        row = await store.find(session, VIDEO_ID)
        assert row is not None
        row.algo_version = 0
        await session.commit()
    assert (await client.get(f"/api/analyses/{VIDEO_ID}")).json()["status"] == "done"

    assert (await _analyze(client)).status_code == 202
    async with store.session() as session:
        row = await store.find(session, VIDEO_ID)
    assert row is not None and row.algo_version == ALGO_VERSION
    assert len(downloads) == 2


async def test_simultaneous_posts_download_once(client):
    responses = await asyncio.gather(_post(client), _post(client))
    while await worker.process_next():
        pass
    assert sorted(r.status_code for r in responses) in ([200, 202], [202, 202])
    assert len(downloads) == 1


async def test_run_skips_download_when_analysis_was_saved_meanwhile(client):
    await _analyze(client)
    downloads.clear()
    async with store.session() as session:
        assert await jobs.start(session, VIDEO_ID) is True
    assert await worker.process_next() is True
    assert downloads == []
    async with store.session() as session:
        assert await jobs.get(session, VIDEO_ID) is None


async def test_list_is_newest_first_with_summary(client):
    await _analyze(client)
    await _analyze(client, "https://youtu.be/aaaaaaaaaaa")
    items = (await client.get("/api/analyses")).json()
    assert [i["video_id"] for i in items] == ["aaaaaaaaaaa", VIDEO_ID]
    first = items[0]
    assert first["title"] == "Dois Passarinhos"
    assert first["duration_seconds"] == 120
    assert first["top_note"]["name"] == "B4"
    assert first["created_at"]


async def test_old_error_jobs_are_discarded(monkeypatch):
    monkeypatch.setattr(jobs, "MAX_JOBS", 2)
    async with store.session() as session:
        for video_id in ("aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"):
            await jobs.start(session, video_id)
            await jobs.fail(session, video_id, "falhou")
        assert await jobs.get(session, "aaaaaaaaaaa") is None
        assert await jobs.get(session, "ccccccccccc") is not None


async def test_running_jobs_are_never_discarded(monkeypatch):
    monkeypatch.setattr(jobs, "MAX_JOBS", 2)
    async with store.session() as session:
        for video_id in ("aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"):
            await jobs.start(session, video_id)
        assert await jobs.get(session, "aaaaaaaaaaa") is not None


async def test_start_refuses_running_job_and_reuses_failed_one():
    async with store.session() as session:
        assert await jobs.start(session, VIDEO_ID) is True
        assert await jobs.start(session, VIDEO_ID) is False
        await jobs.fail(session, VIDEO_ID, "falhou")
        assert await jobs.start(session, VIDEO_ID) is True
        progress = await jobs.get(session, VIDEO_ID)
    assert progress == jobs.Progress("pending")


async def test_post_leaves_job_pending_until_worker_runs(client):
    assert (await _post(client)).status_code == 202
    assert (await client.get(f"/api/analyses/{VIDEO_ID}")).json()["status"] == "pending"
    assert downloads == []
    assert await worker.process_next() is True
    assert (await client.get(f"/api/analyses/{VIDEO_ID}")).json()["status"] == "done"


async def test_claim_gives_each_pending_job_once_oldest_first():
    async with store.session() as session:
        await jobs.start(session, "aaaaaaaaaaa")
        await jobs.start(session, "bbbbbbbbbbb")
        assert await jobs.claim(session) == "aaaaaaaaaaa"
        assert await jobs.get(session, "aaaaaaaaaaa") == jobs.Progress("downloading")
        assert await jobs.claim(session) == "bbbbbbbbbbb"
        assert await jobs.claim(session) is None


async def test_requeue_orphans_returns_running_jobs_to_pending_and_keeps_errors():
    async with store.session() as session:
        await jobs.start(session, "aaaaaaaaaaa")
        await jobs.claim(session)
        await jobs.start(session, "bbbbbbbbbbb")
        await jobs.fail(session, "bbbbbbbbbbb", "falhou")
        assert await jobs.requeue_orphans(session) == 1
        assert await jobs.get(session, "aaaaaaaaaaa") == jobs.Progress("pending")
        assert await jobs.get(session, "bbbbbbbbbbb") == jobs.Progress("error", "falhou")


async def test_ceilings_endpoint_lists_options(client):
    body = (await client.get("/api/ceilings")).json()
    assert len(body["options"]) == 25
    assert body["default_midi"] == 66
    assert body["options"][0] == {"midi": 48, "name": "C3"}


async def test_lifespan_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DomainError, match="DATABASE_URL"):
        async with app.router.lifespan_context(app):
            pass


async def test_failed_reanalysis_keeps_old_report_readable(client, monkeypatch):
    await _analyze(client)
    async with store.session() as session:
        row = await store.find(session, VIDEO_ID)
        assert row is not None
        row.algo_version = 0
        await session.commit()

    def failing(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
        raise DownloadError("Não consegui baixar o áudio deste vídeo.")

    monkeypatch.setattr(worker, "download_audio", failing)
    assert (await _analyze(client)).status_code == 202
    body = (await client.get(f"/api/analyses/{VIDEO_ID}")).json()
    assert body["status"] == "done"
    assert body["report"] is not None


async def test_delete_removes_from_list_and_report(client):
    await _analyze(client)
    await _analyze(client, "https://youtu.be/aaaaaaaaaaa")
    assert (await client.delete(f"/api/analyses/{VIDEO_ID}")).status_code == 204
    assert [i["video_id"] for i in (await client.get("/api/analyses")).json()] == ["aaaaaaaaaaa"]
    assert (await client.get(f"/api/analyses/{VIDEO_ID}")).status_code == 404


async def test_delete_unknown_is_404(client):
    assert (await client.delete(f"/api/analyses/{VIDEO_ID}")).status_code == 404


async def test_delete_during_reanalysis_is_409_and_keeps_record(client):
    await _analyze(client)
    async with store.session() as session:
        await jobs.start(session, VIDEO_ID)
    assert (await client.delete(f"/api/analyses/{VIDEO_ID}")).status_code == 409
    assert (await client.get("/api/analyses")).json()[0]["video_id"] == VIDEO_ID


async def test_delete_then_analyze_again_downloads_again(client):
    await _analyze(client)
    await client.delete(f"/api/analyses/{VIDEO_ID}")
    assert (await _analyze(client)).status_code == 202
    assert len(downloads) == 2


async def test_rate_limit_blocks_new_jobs_per_ip_but_not_reuse(client, monkeypatch):
    monkeypatch.setenv("MAX_REQUESTS_PER_HOUR", "2")
    assert (await _post(client, "https://youtu.be/aaaaaaaaaaa")).status_code == 202
    # Job já existente não conta nem é bloqueado.
    assert (await _post(client, "https://youtu.be/aaaaaaaaaaa")).status_code == 202
    assert (await _post(client, "https://youtu.be/bbbbbbbbbbb")).status_code == 202
    blocked = await _post(client, "https://youtu.be/ccccccccccc")
    assert blocked.status_code == 429
    assert "limite" in blocked.json()["detail"].lower()
    async with store.session() as session:
        assert await jobs.get(session, "ccccccccccc") is None
    # Análise guardada também não conta.
    while await worker.process_next():
        pass
    assert (await _post(client, "https://youtu.be/aaaaaaaaaaa")).status_code == 200


async def test_jobs_list_shows_queue_and_failures(client, monkeypatch):
    def no_melody(path: Path):
        raise NoMelodyError("Sem melodia.")

    await _post(client, "https://youtu.be/aaaaaaaaaaa")
    queued = (await client.get("/api/jobs")).json()
    assert [(j["video_id"], j["status"]) for j in queued] == [("aaaaaaaaaaa", "pending")]
    monkeypatch.setattr(worker, "analyze_audio", no_melody)
    while await worker.process_next():
        pass
    failed = (await client.get("/api/jobs")).json()
    assert [(j["video_id"], j["status"]) for j in failed] == [("aaaaaaaaaaa", "error")]
    assert failed[0]["error"] == "Sem melodia."


async def test_dismiss_removes_failure_but_not_the_saved_analysis(client):
    await _analyze(client)
    async with store.session() as session:
        await jobs.start(session, VIDEO_ID)
        await jobs.fail(session, VIDEO_ID, "falhou")
    assert (await client.delete(f"/api/jobs/{VIDEO_ID}")).status_code == 204
    assert (await client.get("/api/jobs")).json() == []
    assert [i["video_id"] for i in (await client.get("/api/analyses")).json()] == [VIDEO_ID]


async def test_dismiss_queued_job_is_409(client):
    await _post(client)
    assert (await client.delete(f"/api/jobs/{VIDEO_ID}")).status_code == 409
