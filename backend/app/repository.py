"""All SQL for documents and chunks lives here. Callers pass in a connection
and decide when to commit, so one upload can be a single transaction."""
from collections.abc import Sequence

import psycopg
from pgvector import Vector

from app.chunking import Chunk


def create_document(conn: psycopg.Connection, filename: str, file_type: str) -> int:
    row = conn.execute(
        "INSERT INTO documents (filename, file_type) VALUES (%s, %s) RETURNING id",
        (filename, file_type),
    ).fetchone()
    return row[0]


def set_status(conn: psycopg.Connection, doc_id: int, status: str, error: str | None = None) -> None:
    conn.execute("UPDATE documents SET status = %s, error = %s WHERE id = %s", (status, error, doc_id))


def add_chunks(
    conn: psycopg.Connection,
    doc_id: int,
    chunks: Sequence[Chunk],
    embeddings: Sequence[Sequence[float]] | None = None,
) -> None:
    if embeddings is not None and len(embeddings) != len(chunks):
        raise ValueError("embeddings and chunks must have the same length")
    rows = [
        (doc_id, c.chunk_index, c.text, c.heading, c.page, c.source, c.flags, c.quarantined,
         Vector(list(embeddings[i])) if embeddings is not None else None)
        for i, c in enumerate(chunks)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO chunks (document_id, chunk_index, text, heading, page, source, flags, quarantined, embedding) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )


def list_documents(conn: psycopg.Connection) -> list[dict]:
    cur = conn.execute(
        "SELECT d.id, d.filename, d.file_type, d.status, d.error, d.created_at, "
        "       (SELECT count(*) FROM chunks c WHERE c.document_id = d.id), "
        "       (SELECT count(*) FROM chunks c WHERE c.document_id = d.id AND c.quarantined), "
        "       (SELECT count(*) FROM chunks c WHERE c.document_id = d.id AND 'sanitized' = ANY(c.flags)), "
        "       (SELECT COALESCE(array_agg(DISTINCT f ORDER BY f), '{}') "
        "          FROM chunks c, unnest(c.flags) AS f WHERE c.document_id = d.id) "
        "FROM documents d ORDER BY d.id DESC"
    )
    # quarantined / sanitized / flags are derived from the chunks, so the library page can show scanner
    # results after a reload (the upload response alone is gone once the page refreshes).
    keys = ["id", "filename", "file_type", "status", "error", "created_at", "chunk_count",
            "quarantined", "sanitized", "flags"]
    return [dict(zip(keys, r)) for r in cur.fetchall()]


def delete_document(conn: psycopg.Connection, doc_id: int) -> bool:
    """Chunks are removed by ON DELETE CASCADE. Returns True if the document existed."""
    return conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,)).rowcount > 0
