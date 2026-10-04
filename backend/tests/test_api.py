import uuid

import pytest
from fastapi.testclient import TestClient

from app import main
from app.db import get_conn
from app.main import app, embedder_dep
from tests.fakes import FailingEmbedder, HashEmbedder

plain = TestClient(app)  # for requests that are rejected before the database is touched


def _upload(c, name: str, data: bytes):
    return c.post("/documents/upload", files={"file": (name, data)})


def _name(suffix: str) -> str:
    return f"apitest-{uuid.uuid4().hex[:8]}-{suffix}"


@pytest.fixture()
def client(db_ready):
    app.dependency_overrides[embedder_dep] = lambda: HashEmbedder()
    yield TestClient(app)
    app.dependency_overrides.clear()
    with get_conn() as c:
        c.execute("DELETE FROM documents WHERE filename LIKE 'apitest-%'")


# ---- rejected before the database ----
def test_health():
    assert plain.get("/health").json() == {"status": "ok"}


def test_rejects_bad_type():
    assert _upload(plain, "evil.exe", b"MZ...").status_code == 415


def test_rejects_empty():
    assert _upload(plain, "a.txt", b"").status_code == 400


def test_rejects_malformed():
    assert _upload(plain, "a.txt", b"abc\x00").status_code == 422


def test_rejects_file_without_text():
    assert _upload(plain, "a.txt", b"  \n\n  ").status_code == 422


def test_rejects_oversize(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    assert _upload(plain, "a.txt", b"x" * 50).status_code == 413


# ---- full pipeline (needs Postgres; skipped otherwise) ----
def test_upload_indexes_document(client):
    name = _name("doc.md")
    r = _upload(client, name, b"# Setup\nInstall the thing.\n\n# Usage\nRun the thing.\n")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "indexed" and body["chunks"] == 2 and body["preview"][0]["heading"] == "Setup"

    with get_conn() as c:
        n = c.execute(
            "SELECT count(*) FROM chunks WHERE document_id = %s AND embedding IS NOT NULL", (body["document_id"],)
        ).fetchone()[0]
    assert n == 2

    docs = {d["id"]: d for d in client.get("/documents").json()}
    assert docs[body["document_id"]]["status"] == "indexed"
    assert docs[body["document_id"]]["chunk_count"] == 2


def test_path_traversal_filename_is_flattened(client):
    name = _name("notes.txt")
    r = _upload(client, f"../../etc/{name}", b"hello world")
    assert r.status_code == 200 and r.json()["filename"] == name


def test_delete_document(client):
    doc_id = _upload(client, _name("d.txt"), b"some text").json()["document_id"]
    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.delete(f"/documents/{doc_id}").status_code == 404
    assert doc_id not in {d["id"] for d in client.get("/documents").json()}


def test_embedding_failure_is_recorded_not_silent(client):
    app.dependency_overrides[embedder_dep] = lambda: FailingEmbedder()
    name = _name("bad.txt")
    r = _upload(client, name, b"some text")
    assert r.status_code == 500 and "boom" in r.json()["detail"]

    doc = next(d for d in client.get("/documents").json() if d["filename"] == name)
    assert doc["status"] == "failed" and "boom" in doc["error"] and doc["chunk_count"] == 0


def test_search_endpoint(client):
    doc = _upload(client, _name("s.md"), b"# Databases\nPostgreSQL stores vectors with pgvector.\n\n# Fruit\nBananas are yellow.\n").json()
    r = client.post("/search", json={"query": "which database stores vectors", "k": 2, "document_ids": [doc["document_id"]]})
    assert r.status_code == 200
    hits = r.json()
    assert hits[0]["heading"] == "Databases" and hits[0]["source"].endswith("s.md")


def test_search_validates_input():
    assert plain.post("/search", json={"query": ""}).status_code == 422
    assert plain.post("/search", json={"query": "x" * 501}).status_code == 422
    assert plain.post("/search", json={"query": "ok", "mode": "magic"}).status_code == 422
