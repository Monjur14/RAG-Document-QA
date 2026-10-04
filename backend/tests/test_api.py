from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def _upload(name: str, data: bytes):
    return client.post("/documents/upload", files={"file": (name, data)})


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_markdown_ok():
    r = _upload("doc.md", b"# Hi\nsome text here\n")
    assert r.status_code == 200
    body = r.json()
    assert body["file_type"] == "md" and body["sections"] == 1
    assert body["preview"][0]["heading"] == "Hi"


def test_upload_rejects_bad_type():
    assert _upload("evil.exe", b"MZ...").status_code == 415


def test_upload_rejects_empty():
    assert _upload("a.txt", b"").status_code == 400


def test_upload_rejects_malformed():
    assert _upload("a.txt", b"abc\x00").status_code == 422


def test_upload_rejects_oversize(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    assert _upload("a.txt", b"x" * 50).status_code == 413


def test_path_traversal_filename_is_flattened():
    r = _upload("../../etc/notes.txt", b"hello")
    assert r.status_code == 200 and r.json()["filename"] == "notes.txt"
