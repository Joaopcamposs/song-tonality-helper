from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_serves_the_front():
    response = client.get("/")
    assert response.status_code == 200
    assert "Tonalidade" in response.text


def test_api_routes_still_win_over_static_files():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_front_has_the_login_screen_and_no_passphrase():
    html = client.get("/").text
    for element_id in ("auth", "auth-form", "logout"):
        assert f'id="{element_id}"' in html
    assert 'id="gate' not in html
    script = client.get("/app.js").text
    assert "passphrase" not in script.lower()
    assert "X-App-Passphrase" not in script
    assert "localStorage.getItem(CEILING_KEY)" not in script
