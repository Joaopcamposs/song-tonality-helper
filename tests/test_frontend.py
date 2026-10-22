from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_serves_the_front():
    response = client.get("/")
    assert response.status_code == 200
    assert "Song Tonality Helper" in response.text


def test_api_routes_still_win_over_static_files():
    assert client.get("/api/health").json() == {"status": "ok"}
