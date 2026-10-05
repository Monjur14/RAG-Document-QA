"""The production wrapper: API under /api, the built frontend at /, client-side routes fall back to index.html."""
import pytest
from fastapi.testclient import TestClient

from app.web import create_web


@pytest.fixture
def client(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Document Q&A</title>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return TestClient(create_web(tmp_path))


def test_api_is_served_under_api(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_root_and_client_routes_serve_the_app(client):
    for path in ("/", "/chat", "/metrics"):
        r = client.get(path)
        assert r.status_code == 200 and "Document Q&A" in r.text


def test_static_assets_are_served_and_missing_ones_stay_404(client):
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/assets/missing.js").status_code == 404


def test_unknown_api_route_is_a_json_404_not_the_app(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_security_headers(client):
    h = client.get("/").headers
    assert "default-src 'self'" in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert "content-security-policy" not in client.get("/api/docs").headers  # Swagger UI needs its CDN


def test_without_a_build_only_the_api_is_served(tmp_path):
    c = TestClient(create_web(tmp_path / "no-build"))
    assert c.get("/api/health").status_code == 200
    assert c.get("/").status_code == 404
