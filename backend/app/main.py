import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app import repository as repo
from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB
from app.cache import answer_with_cache
from app.db import get_conn
from app.embeddings import Embedder, get_embedder
from app.metrics import log_request, summary
from app.ingest import EmptyDocument, IngestionFailed, ingest_document
from app.models import AskRequest, AskResponse, DocumentInfo, SearchHit, SearchRequest, UploadResponse
from app.parsers import MalformedFile, UnsupportedFormat
from app.providers import LLMProvider, ProviderError, get_provider
from app.ratelimit import rate_limit
from app.retrieval import search

app = FastAPI(title="Secure RAG Document Q&A")


# Dependencies are functions so tests can swap in a fake embedder / different database.
def embedder_dep() -> Embedder:
    return get_embedder()


def provider_dep() -> LLMProvider:
    return get_provider()


def reranker_dep():
    if not config.RERANK_ENABLED:
        return None
    from app.rerank import get_reranker

    return get_reranker()


def connect_dep() -> Callable[[], psycopg.Connection]:
    return get_conn


def _with_conn(connect: Callable[[], psycopg.Connection], fn):
    conn = connect()
    try:
        return fn(conn)
    finally:
        conn.close()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents/upload", response_model=UploadResponse, dependencies=[Depends(rate_limit("upload"))])
async def upload_document(
    file: UploadFile,
    embedder: Embedder = Depends(embedder_dep),
    connect: Callable = Depends(connect_dep),
) -> UploadResponse:
    # Use only the base name; never trust client-supplied paths.
    filename = Path(file.filename or "").name
    ext = Path(filename).suffix.lower()
    if not filename or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Unsupported file type. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    # Read at most limit+1 bytes so oversized uploads are rejected without loading them fully.
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")
    if not raw:
        raise HTTPException(400, "File is empty")

    try:
        # Parsing, embedding and SQL are blocking work: keep them off the event loop.
        result = await run_in_threadpool(ingest_document, connect, embedder, filename, raw)
    except UnsupportedFormat as exc:
        raise HTTPException(415, str(exc)) from exc
    except (MalformedFile, EmptyDocument) as exc:
        raise HTTPException(422, str(exc)) from exc
    except IngestionFailed as exc:
        raise HTTPException(500, f"Indexing failed for document {exc.document_id}: {exc}") from exc
    except psycopg.OperationalError as exc:
        raise HTTPException(503, "Database unavailable") from exc

    return UploadResponse(status="indexed", **result.__dict__)


@app.get("/documents", response_model=list[DocumentInfo])
async def list_documents(connect: Callable = Depends(connect_dep)) -> list[dict]:
    try:
        return await run_in_threadpool(_with_conn, connect, repo.list_documents)
    except psycopg.OperationalError as exc:
        raise HTTPException(503, "Database unavailable") from exc


@app.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: int, connect: Callable = Depends(connect_dep)) -> Response:
    def work(conn: psycopg.Connection) -> bool:
        found = repo.delete_document(conn, doc_id)
        conn.commit()
        return found

    try:
        found = await run_in_threadpool(_with_conn, connect, work)
    except psycopg.OperationalError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    if not found:
        raise HTTPException(404, "Document not found")
    return Response(status_code=204)


@app.post("/search", response_model=list[SearchHit])
async def search_chunks(
    req: SearchRequest,
    embedder: Embedder = Depends(embedder_dep),
    connect: Callable = Depends(connect_dep),
) -> list[SearchHit]:
    def work(conn: psycopg.Connection):
        return search(
            conn, embedder, req.query, k=req.k, mode=req.mode,
            file_types=req.file_types, document_ids=req.document_ids,
        )

    try:
        hits = await run_in_threadpool(_with_conn, connect, work)
    except psycopg.OperationalError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return [SearchHit(**h.__dict__) for h in hits]


@app.get("/metrics")
async def metrics(hours: float | None = None, connect: Callable = Depends(connect_dep)) -> dict:
    """Cost, tokens, latency percentiles, cache hit rate and error rate (all time, or the last `hours`)."""
    try:
        return await run_in_threadpool(_with_conn, connect, lambda conn: summary(conn, hours))
    except psycopg.OperationalError as exc:
        raise HTTPException(503, "Database unavailable") from exc


@app.post("/ask", response_model=AskResponse, dependencies=[Depends(rate_limit("ask"))])
async def ask(
    req: AskRequest,
    embedder: Embedder = Depends(embedder_dep),
    provider: LLMProvider = Depends(provider_dep),
    reranker=Depends(reranker_dep),
    connect: Callable = Depends(connect_dep),
) -> AskResponse:
    def work(conn: psycopg.Connection):
        t0 = time.perf_counter()
        try:
            result = answer_with_cache(
                conn, embedder, provider, req.question, k=req.k, mode=req.mode,
                file_types=req.file_types, document_ids=req.document_ids, reranker=reranker,
            )
        except ProviderError as exc:
            log_request(conn, question=req.question, status="error", error=type(exc).__name__,
                        latency_ms=(time.perf_counter() - t0) * 1000, model=getattr(provider, "model", None))
            raise
        log_request(conn, question=req.question, status=result.status, latency_ms=result.latency_ms,
                    cache=result.cache, model=result.model, prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
                    retrieved=result.retrieved, confidence=result.confidence)
        return result

    try:
        result = await run_in_threadpool(_with_conn, connect, work)
    except ProviderError as exc:
        raise HTTPException(502, f"The language model is unavailable: {exc}") from exc
    except psycopg.OperationalError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return AskResponse(**asdict(result))
