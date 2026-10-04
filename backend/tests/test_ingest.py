import uuid

import pytest

from app.chunking import ChunkConfig
from app.db import get_conn
from app.ingest import EmptyDocument, IngestionFailed, ingest_document
from app.parsers import UnsupportedFormat
from tests.fakes import FailingEmbedder, HashEmbedder


@pytest.fixture()
def prefix(db_ready):
    p = f"ingesttest-{uuid.uuid4().hex[:8]}"
    yield p
    with get_conn() as c:
        c.execute("DELETE FROM documents WHERE filename LIKE %s", (f"{p}%",))


def test_ingest_stores_chunks_with_metadata_and_embeddings(prefix):
    md = b"# Alpha\n" + b"word " * 300 + b"\n\n# Beta\nshort section\n"
    res = ingest_document(get_conn, HashEmbedder(), f"{prefix}.md", md, ChunkConfig(chunk_size=400, overlap=50))
    assert res.chunks >= 3 and res.sections == 2

    with get_conn() as c:
        rows = c.execute(
            "SELECT heading, chunk_index, embedding IS NOT NULL FROM chunks WHERE document_id = %s ORDER BY chunk_index",
            (res.document_id,),
        ).fetchall()
        status = c.execute("SELECT status FROM documents WHERE id = %s", (res.document_id,)).fetchone()[0]
    assert status == "indexed"
    assert [r[1] for r in rows] == list(range(res.chunks))
    assert all(r[2] for r in rows)
    assert rows[0][0] == "Alpha" and rows[-1][0] == "Beta"


def test_failed_embedding_leaves_no_chunks_and_marks_document_failed(prefix):
    with pytest.raises(IngestionFailed) as exc:
        ingest_document(get_conn, FailingEmbedder(), f"{prefix}.txt", b"hello there")
    with get_conn() as c:
        status, err = c.execute("SELECT status, error FROM documents WHERE id = %s", (exc.value.document_id,)).fetchone()
        n = c.execute("SELECT count(*) FROM chunks WHERE document_id = %s", (exc.value.document_id,)).fetchone()[0]
    assert (status, err, n) == ("failed", "boom", 0)


def test_parse_errors_never_touch_the_database():
    def no_db():
        raise AssertionError("database must not be used")

    with pytest.raises(UnsupportedFormat):
        ingest_document(no_db, HashEmbedder(), "x.exe", b"abc")
    with pytest.raises(EmptyDocument):
        ingest_document(no_db, HashEmbedder(), "x.txt", b"   \n\n  ")
