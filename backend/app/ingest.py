"""Ingestion pipeline: parse -> chunk -> embed -> store.

A document row is committed (status 'pending') before the slow/risky steps, so a failure is
recorded on the document as status 'failed' with the reason, never silent and never half-indexed.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from app import config
from app import repository as repo
from app.chunking import ChunkConfig, chunk_sections
from app.embeddings import Embedder, chunk_embedding_text
from app.models import ParsedSection
from app.sandbox import parse_upload
from app.scanner import scan_text


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
    quarantined: int = 0                       # chunks stored but excluded from retrieval
    sanitized: int = 0                         # chunks kept after cutting out an attack paragraph
    flags: list[str] = field(default_factory=list)   # distinct scanner findings


def _scan_chunks(chunks) -> list[str]:
    """Scan every chunk: strip invisible characters, cut out paragraphs that carry an injection, and quarantine a
    chunk only when nothing worth keeping is left. Returns the distinct flags found. Quarantined chunks stay in the
    database (so nothing silently disappears) but are filtered out of every search."""
    found: list[str] = []
    for c in chunks:
        r = scan_text(c.text)
        c.text, c.flags, c.quarantined = r.clean_text, r.flags, r.quarantine
        found += [f for f in r.flags if f not in found]
    return found


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
    sections = parse_upload(filename, raw)
    if not sections:
        hint = " (scanned PDF? OCR is not supported yet)" if file_type == "pdf" else ""
        raise EmptyDocument("No extractable text found in file" + hint)
    chunks = chunk_sections(sections, cfg)
    flags = _scan_chunks(chunks) if config.SCAN_ENABLED else []

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
        quarantined=sum(c.quarantined for c in chunks),
        sanitized=sum("sanitized" in c.flags for c in chunks),
        flags=flags,
    )
