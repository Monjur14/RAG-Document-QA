"""Retrieval: vector search, keyword search, and hybrid (reciprocal rank fusion).

Scores are not comparable across modes:
- vector:  cosine similarity (0..1, higher is closer)  -> also used later for the "I don't know" threshold
- keyword: Postgres ts_rank_cd
- hybrid:  reciprocal rank fusion score; `vector_score` still carries the cosine similarity
"""
import re
from dataclasses import dataclass, replace
from typing import Literal

import psycopg
from pgvector import Vector

from app.embeddings import Embedder

Mode = Literal["vector", "keyword", "hybrid"]


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    chunk_index: int
    source: str
    heading: str | None
    page: int | None
    text: str
    score: float
    vector_score: float | None = None   # cosine similarity, when the chunk came from vector search
    vector_rank: int | None = None      # 1-based rank in the vector candidate list
    keyword_rank: int | None = None     # 1-based rank in the keyword candidate list
    rerank_score: float | None = None   # cross-encoder score, when the hit was reranked


_COLUMNS = "c.id, c.document_id, c.chunk_index, c.source, c.heading, c.page, c.text"


def _filters(file_types: list[str] | None, document_ids: list[int] | None) -> tuple[str, dict]:
    clauses = ["d.status = 'indexed'"]  # never search documents that are pending or failed
    params: dict = {}
    if file_types:
        clauses.append("d.file_type = ANY(%(file_types)s)")
        params["file_types"] = [t.lower().lstrip(".") for t in file_types]
    if document_ids:
        clauses.append("d.id = ANY(%(document_ids)s)")
        params["document_ids"] = list(document_ids)
    return " AND ".join(clauses), params


def vector_search(
    conn: psycopg.Connection,
    embedding: list[float],
    k: int,
    file_types: list[str] | None = None,
    document_ids: list[int] | None = None,
) -> list[RetrievedChunk]:
    where, params = _filters(file_types, document_ids)
    params.update(q=Vector(embedding), k=k)
    rows = conn.execute(
        f"SELECT {_COLUMNS}, 1 - (c.embedding <=> %(q)s) AS sim "
        f"FROM chunks c JOIN documents d ON d.id = c.document_id "
        f"WHERE {where} AND c.embedding IS NOT NULL "
        f"ORDER BY c.embedding <=> %(q)s LIMIT %(k)s",
        params,
    ).fetchall()
    return [
        RetrievedChunk(*r[:7], score=float(r[7]), vector_score=float(r[7]), vector_rank=i)
        for i, r in enumerate(rows, 1)
    ]


def _or_query(text: str) -> str:
    """'How do I reset it?' -> 'how | do | i | reset | it'. Letters/digits only, so it is safe to
    pass to to_tsquery. OR semantics: a natural-language question rarely contains every word of a passage."""
    words = dict.fromkeys(w.lower() for w in re.findall(r"[^\W_]+", text))
    return " | ".join(words)


def keyword_search(
    conn: psycopg.Connection,
    text: str,
    k: int,
    file_types: list[str] | None = None,
    document_ids: list[int] | None = None,
) -> list[RetrievedChunk]:
    tsq = _or_query(text)
    if not tsq:
        return []
    where, params = _filters(file_types, document_ids)
    params.update(tsq=tsq, k=k)
    rows = conn.execute(
        f"SELECT {_COLUMNS}, ts_rank_cd(c.tsv, q, 32) AS rank "
        f"FROM chunks c JOIN documents d ON d.id = c.document_id, to_tsquery('english', %(tsq)s) q "
        f"WHERE {where} AND c.tsv @@ q "
        f"ORDER BY rank DESC, c.id LIMIT %(k)s",
        params,
    ).fetchall()
    return [RetrievedChunk(*r[:7], score=float(r[7]), keyword_rank=i) for i, r in enumerate(rows, 1)]


def rrf_merge(
    vector_hits: list[RetrievedChunk], keyword_hits: list[RetrievedChunk], rrf_k: int = 60
) -> list[RetrievedChunk]:
    """Reciprocal rank fusion: score = sum over lists of 1 / (rrf_k + rank). Needs only ranks, so the
    incomparable cosine and ts_rank scores never have to be normalised."""
    merged: dict[int, RetrievedChunk] = {}
    for rank, h in enumerate(vector_hits, 1):
        m = merged.setdefault(h.chunk_id, replace(h, score=0.0))
        m.vector_rank, m.vector_score = rank, h.vector_score
        m.score += 1.0 / (rrf_k + rank)
    for rank, h in enumerate(keyword_hits, 1):
        m = merged.setdefault(h.chunk_id, replace(h, score=0.0))
        m.keyword_rank = rank
        m.score += 1.0 / (rrf_k + rank)
    return sorted(merged.values(), key=lambda h: (-h.score, h.chunk_id))


def search(
    conn: psycopg.Connection,
    embedder: Embedder,
    query: str,
    *,
    k: int = 5,
    mode: Mode = "hybrid",
    file_types: list[str] | None = None,
    document_ids: list[int] | None = None,
    candidates: int = 50,
    reranker=None,
    rerank_pool: int = 20,
) -> list[RetrievedChunk]:
    """Top-k chunks for a question. `candidates` is how many each retriever contributes to the fusion.
    With a `reranker`, the top `rerank_pool` hits of the chosen mode are re-scored and cut to k."""
    if reranker is not None:
        from app.rerank import rerank

        pool = search(conn, embedder, query, k=max(rerank_pool, k), mode=mode, file_types=file_types,
                      document_ids=document_ids, candidates=candidates)
        return rerank(query, pool, reranker, k)
    if mode == "keyword":
        return keyword_search(conn, query, k, file_types, document_ids)
    q = embedder.embed_query(query)
    if mode == "vector":
        return vector_search(conn, q, k, file_types, document_ids)
    if mode == "hybrid":
        v = vector_search(conn, q, candidates, file_types, document_ids)
        w = keyword_search(conn, query, candidates, file_types, document_ids)
        return rrf_merge(v, w)[:k]
    raise ValueError(f"unknown mode: {mode}")
