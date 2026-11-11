from pathlib import Path

import pytest

from app import worker
from app.domain.features import AudioFeatures
from app.services import jobs, store
from app.services.download import DownloadedAudio

VIDEO_ID = "dQw4w9WgXcQ"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
downloads: list[str] = []


@pytest.fixture(autouse=True)
def fake_pipeline(monkeypatch):
    downloads.clear()

    def fake_download(video_id: str, dest_dir: Path, proxy: str | None = None) -> DownloadedAudio:
        downloads.append(video_id)
        return DownloadedAudio(dest_dir / "audio.wav", "Música", 100)

    features = AudioFeatures(
        top_midi=71, ranking=[(71, 150)], top_times=[1.0], chroma_windows=[[0.1] * 12]
    )
    monkeypatch.setattr(worker, "download_audio", fake_download)
    monkeypatch.setattr(worker, "analyze_audio", lambda path: features)


async def drain() -> None:
    while await worker.process_next():
        pass


async def test_other_user_cannot_see_or_delete(make_client):
    ana = await make_client("ana@x.com")
    bia = await make_client("bia@x.com")
    await ana.post("/api/analyses", json={"url": URL})
    await drain()
    assert (await bia.get("/api/analyses")).json() == []
    assert (await bia.get("/api/jobs")).json() == []
    assert (await bia.get(f"/api/analyses/{VIDEO_ID}")).status_code == 404
    assert (await bia.delete(f"/api/analyses/{VIDEO_ID}")).status_code == 404
    assert (await bia.delete(f"/api/jobs/{VIDEO_ID}")).status_code == 404
    assert (await ana.get(f"/api/analyses/{VIDEO_ID}")).json()["status"] == "done"


async def test_same_video_two_users_downloads_once_and_delete_is_per_user(make_client):
    ana = await make_client("ana@x.com")
    bia = await make_client("bia@x.com")
    first = await ana.post("/api/analyses", json={"url": URL})
    second = await bia.post("/api/analyses", json={"url": URL})  # job de Ana ainda na fila
    assert (first.status_code, second.status_code) == (202, 202)
    await drain()
    assert downloads == [VIDEO_ID]
    for client in (ana, bia):
        assert [i["video_id"] for i in (await client.get("/api/analyses")).json()] == [VIDEO_ID]
    assert (await ana.delete(f"/api/analyses/{VIDEO_ID}")).status_code == 204
    assert (await ana.get("/api/analyses")).json() == []
    assert (await bia.get(f"/api/analyses/{VIDEO_ID}")).json()["status"] == "done"
    late = await ana.post("/api/analyses", json={"url": URL})  # já analisada: só religa
    assert late.status_code == 200
    assert downloads == [VIDEO_ID]


async def test_saved_ceiling_is_default_and_preview_does_not_save(logged_client):
    await logged_client.post("/api/analyses", json={"url": URL})
    await drain()
    default = (await logged_client.get("/api/me/settings")).json()["ceiling_midi"]
    shift_default = (await logged_client.get(f"/api/analyses/{VIDEO_ID}")).json()["report"]["shift"]
    saved = await logged_client.put("/api/me/settings", json={"ceiling_midi": 60})
    assert saved.json() == {"ceiling_midi": 60}
    assert default != 60
    report = (await logged_client.get(f"/api/analyses/{VIDEO_ID}")).json()["report"]
    assert report["ceiling"]["midi"] == 60
    assert report["shift"] != shift_default
    preview = (await logged_client.get(f"/api/analyses/{VIDEO_ID}?ceiling_midi=65")).json()
    assert preview["report"]["ceiling"]["midi"] == 65
    assert (await logged_client.get("/api/me/settings")).json()["ceiling_midi"] == 60
    assert len(downloads) == 1


@pytest.mark.parametrize("midi", [47, 73])
async def test_ceiling_out_of_range_is_422(logged_client, midi):
    response = await logged_client.put("/api/me/settings", json={"ceiling_midi": midi})
    assert response.status_code == 422


async def test_ceiling_is_per_user(make_client):
    ana = await make_client("ana@x.com")
    bia = await make_client("bia@x.com")
    await ana.put("/api/me/settings", json={"ceiling_midi": 60})
    assert (await bia.get("/api/me/settings")).json()["ceiling_midi"] != 60


async def test_rate_limit_is_per_user(make_client, monkeypatch):
    monkeypatch.setenv("MAX_REQUESTS_PER_HOUR", "1")
    ana = await make_client("ana@x.com")
    bia = await make_client("bia@x.com")
    assert (await ana.post("/api/analyses", json={"url": URL})).status_code == 202
    blocked = await ana.post("/api/analyses", json={"url": "https://youtu.be/aaaaaaaaaaa"})
    assert blocked.status_code == 429
    assert (
        await bia.post("/api/analyses", json={"url": "https://youtu.be/bbbbbbbbbbb"})
    ).status_code == 202


async def test_deleting_last_link_forgets_the_failure(make_client):
    ana = await make_client("ana@x.com")
    await ana.post("/api/analyses", json={"url": URL})
    async with store.session() as session:
        await jobs.fail(session, VIDEO_ID, "falhou")
    assert (await ana.delete(f"/api/jobs/{VIDEO_ID}")).status_code == 204
    assert (await ana.get("/api/jobs")).json() == []
    async with store.session() as session:
        assert await jobs.get(session, VIDEO_ID) is None
