"""Ingestion pipeline: parse -> chunk -> embed -> store.

A document row is committed (status 'pending') before the slow/risky steps, so a failure is
recorded on the document as status 'failed' with the reason, never silent and never half-indexed.
"""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import psycopg

from app import repository as repo
from app.chunking import ChunkConfig, chunk_sections
from app.embeddings import Embedder, chunk_embedding_text
from app.models import ParsedSection
from app.parsers import parse_file


class EmptyDocument(ValueError):
    pass


class IngestionFailed(RuntimeError):
    def __init__(self, document_id: int, reason: str):
        super().__init__(reason)
        self.document_id = document_id


@dataclass
class IngestResult:
    document_id: int
    filename: str
    file_type: str
    sections: int
    chunks: int
    characters: int
    preview: list[ParsedSection]


def ingest_document(
    connect: Callable[[], psycopg.Connection],
    embedder: Embedder,
    filename: str,
    raw: bytes,
    cfg: ChunkConfig | None = None,
) -> IngestResult:
    """Raises UnsupportedFormat / MalformedFile / EmptyDocument before touching the database,
    and IngestionFailed (after recording the failure) if embedding or storing goes wrong."""
    file_type = Path(filename).suffix.lower().lstrip(".")
    sections = parse_file(filename, raw)
    if not sections:
        hint = " (scanned PDF? OCR is not supported yet)" if file_type == "pdf" else ""
        raise EmptyDocument("No extractable text found in file" + hint)
    chunks = chunk_sections(sections, cfg)

    conn = connect()
    try:
        doc_id = repo.create_document(conn, filename, file_type)
        conn.commit()
        try:
            embeddings = embedder.embed_documents([chunk_embedding_text(c) for c in chunks])
            repo.add_chunks(conn, doc_id, chunks, embeddings)
            repo.set_status(conn, doc_id, "indexed")
            conn.commit()
        except Exception as exc:
            conn.rollback()
            repo.set_status(conn, doc_id, "failed", str(exc)[:500])
            conn.commit()
            raise IngestionFailed(doc_id, str(exc)) from exc
    finally:
        conn.close()

    return IngestResult(
        document_id=doc_id,
        filename=filename,
        file_type=file_type,
        sections=len(sections),
        chunks=len(chunks),
        characters=sum(len(s.text) for s in sections),
        preview=sections[:3],
    )
