from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.domain.errors import DownloadError, NoMelodyError
from app.domain.pitch import AudioFeatures
from app.main import app
from app.services import jobs

URL = "https://www.youtube.com/watch?v=abc123"
client = TestClient(app)
created_dirs: list[Path] = []


def _features() -> AudioFeatures:
    chroma = np.full((12, 50), 0.05)
    for pc, weight in {7: 1.0, 11: 0.8, 2: 0.9, 9: 0.4, 0: 0.5, 4: 0.5, 6: 0.3}.items():
        chroma[pc, :] = weight
    return AudioFeatures(top_midi=71, ranking=[(71, 150)], top_times=[12.3], chroma=chroma)


@pytest.fixture(autouse=True)
def fake_pipeline(monkeypatch):
    jobs._jobs.clear()
    created_dirs.clear()

    def fake_download(url: str, dest_dir: Path) -> Path:
        created_dirs.append(dest_dir)
        path = dest_dir / "audio.wav"
        path.write_bytes(b"RIFF")
        return path

    monkeypatch.setattr(jobs, "download_audio", fake_download)
    monkeypatch.setattr(jobs, "analyze_audio", lambda path: _features())


def _post(url: str = URL, ceiling_midi: int = 66):
    return client.post("/api/analyses", json={"url": url, "ceiling_midi": ceiling_midi})


def test_post_returns_job_id_and_get_reports_done():
    response = _post()
    assert response.status_code == 202
    body = client.get(f"/api/analyses/{response.json()['id']}").json()
    assert body["status"] == "done"
    assert body["report"]["new_key"] == "D maior"
    assert not created_dirs[0].exists()


def test_invalid_url_is_422_and_no_job():
    assert _post(url="https://evil.com/x").status_code == 422
    assert not jobs._jobs


@pytest.mark.parametrize("ceiling", [47, 73])
def test_ceiling_out_of_range_is_422(ceiling):
    assert _post(ceiling_midi=ceiling).status_code == 422


def test_unknown_job_is_404():
    assert client.get("/api/analyses/nao-existe").status_code == 404


def test_download_failure_ends_in_error_status(monkeypatch):
    def failing_download(url: str, dest_dir: Path) -> Path:
        created_dirs.append(dest_dir)
        raise DownloadError("Não consegui baixar o áudio deste vídeo.")

    monkeypatch.setattr(jobs, "download_audio", failing_download)
    body = client.get(f"/api/analyses/{_post().json()['id']}").json()
    assert body["status"] == "error"
    assert body["error"] == "Não consegui baixar o áudio deste vídeo."
    assert body["report"] is None
    assert not created_dirs[0].exists()


def test_no_melody_ends_in_error_status(monkeypatch):
    def silent(path: Path) -> AudioFeatures:
        raise NoMelodyError("Não encontrei uma melodia detectável neste áudio.")

    monkeypatch.setattr(jobs, "analyze_audio", silent)
    body = client.get(f"/api/analyses/{_post().json()['id']}").json()
    assert body["status"] == "error"
    assert "melodia" in body["error"]


def test_unexpected_failure_ends_in_error_status(monkeypatch):
    def broken(path: Path) -> AudioFeatures:
        raise RuntimeError("segredo interno")

    monkeypatch.setattr(jobs, "analyze_audio", broken)
    body = client.get(f"/api/analyses/{_post().json()['id']}").json()
    assert body["status"] == "error"
    assert "segredo interno" not in body["error"]


def test_old_jobs_are_discarded(monkeypatch):
    monkeypatch.setattr(jobs, "MAX_JOBS", 2)
    ids = [_post().json()["id"] for _ in range(3)]
    assert client.get(f"/api/analyses/{ids[0]}").status_code == 404
    assert client.get(f"/api/analyses/{ids[2]}").status_code == 200


def test_ceilings_endpoint_lists_options():
    body = client.get("/api/ceilings").json()
    assert len(body["options"]) == 25
    assert body["default_midi"] == 66
    assert body["options"][0] == {"midi": 48, "user": "C2", "standard": "C3"}
