"""Integration tests. They need Postgres + pgvector (docker compose up -d db) and are
skipped automatically when no database is reachable. Each test rolls back, so nothing persists."""
import psycopg
import pytest
import sqlalchemy.exc

from app import repository as repo
from app.chunking import Chunk
from app.config import DATABASE_URL, EMBEDDING_DIM
from app.db import get_conn, migrate


@pytest.fixture(scope="session")
def _schema():
    try:
        migrate()
    except (psycopg.OperationalError, sqlalchemy.exc.OperationalError) as exc:
        pytest.skip(f"Postgres not available: {exc}")


@pytest.fixture()
def conn(_schema):
    c = get_conn()
    yield c
    c.rollback()
    c.close()


def basis(i: int) -> list[float]:
    v = [0.0] * EMBEDDING_DIM
    v[i] = 1.0
    return v


def make_chunks(texts: list[str]) -> list[Chunk]:
    return [Chunk(text=t, chunk_index=i, source="a.md", heading="H", page=None) for i, t in enumerate(texts)]


def test_create_list_and_delete_cascade(conn):
    doc = repo.create_document(conn, "a.md", "md")
    repo.add_chunks(conn, doc, make_chunks(["one", "two"]))
    docs = [d for d in repo.list_documents(conn) if d["id"] == doc]
    assert docs[0]["chunk_count"] == 2 and docs[0]["status"] == "pending"
    assert repo.delete_document(conn, doc) is True
    left = conn.execute("SELECT count(*) FROM chunks WHERE document_id = %s", (doc,)).fetchone()[0]
    assert left == 0
    assert repo.delete_document(conn, doc) is False


def test_list_documents_reports_scanner_results(conn):
    doc = repo.create_document(conn, "a.md", "md")
    chunks = make_chunks(["clean", "cut", "held back"])
    chunks[1].flags = ["sanitized", "instruction_override"]
    chunks[2].flags, chunks[2].quarantined = ["instruction_override"], True
    repo.add_chunks(conn, doc, chunks)
    d = [x for x in repo.list_documents(conn) if x["id"] == doc][0]
    assert (d["chunk_count"], d["quarantined"], d["sanitized"]) == (3, 1, 1)
    assert d["flags"] == ["instruction_override", "sanitized"]


def test_list_documents_clean_document_has_no_flags(conn):
    doc = repo.create_document(conn, "a.md", "md")
    repo.add_chunks(conn, doc, make_chunks(["one"]))
    d = [x for x in repo.list_documents(conn) if x["id"] == doc][0]
    assert (d["quarantined"], d["sanitized"], d["flags"]) == (0, 0, [])


def test_set_status(conn):
    doc = repo.create_document(conn, "a.md", "md")
    repo.set_status(conn, doc, "failed", "bad file")
    d = [x for x in repo.list_documents(conn) if x["id"] == doc][0]
    assert (d["status"], d["error"]) == ("failed", "bad file")


def test_status_check_constraint(conn):
    doc = repo.create_document(conn, "a.md", "md")
    with pytest.raises(psycopg.errors.CheckViolation):
        repo.set_status(conn, doc, "bogus")


def test_full_text_search(conn):
    doc = repo.create_document(conn, "a.md", "md")
    repo.add_chunks(conn, doc, make_chunks(["PostgreSQL stores vectors", "bananas are yellow"]))
    rows = conn.execute(
        "SELECT text FROM chunks WHERE document_id = %s AND tsv @@ websearch_to_tsquery('english', %s)",
        (doc, "store vector"),
    ).fetchall()
    assert [r[0] for r in rows] == ["PostgreSQL stores vectors"]


def test_vector_nearest_neighbour(conn):
    doc = repo.create_document(conn, "a.md", "md")
    repo.add_chunks(conn, doc, make_chunks(["zero", "one", "two"]), [basis(0), basis(1), basis(2)])
    rows = conn.execute(
        "SELECT text FROM chunks WHERE document_id = %s ORDER BY embedding <=> %s::vector LIMIT 1",
        (doc, basis(1)),
    ).fetchall()
    assert rows[0][0] == "one"


def test_embedding_length_mismatch(conn):
    doc = repo.create_document(conn, "a.md", "md")
    with pytest.raises(ValueError):
        repo.add_chunks(conn, doc, make_chunks(["x", "y"]), [basis(0)])


def test_indexes_exist(conn):
    names = {r[0] for r in conn.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'chunks'")}
    assert {"chunks_embedding_hnsw", "chunks_tsv_gin"} <= names


def test_connections_use_a_connect_timeout(monkeypatch):
    """A stopped database must fail fast, not hang the request (e.g. Docker not running)."""
    import app.db as db

    seen = {}

    def fake_connect(url, **kw):
        seen.update(kw)
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(db.psycopg, "connect", fake_connect)
    with pytest.raises(psycopg.OperationalError):
        db.get_conn("postgresql://x")
    assert seen["connect_timeout"] == db.DB_CONNECT_TIMEOUT_S == 5
