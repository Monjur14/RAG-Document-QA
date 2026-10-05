"""Exact and semantic answer cache.

Exact: the same question (case, spacing and trailing punctuation ignored) under the same settings.
Semantic: a different wording whose embedding is at least SEMANTIC_CACHE_THRESHOLD similar to a cached question.

Safety rules:
  * Only `answered` results are cached. Refusals are cheap and errors must never stick.
  * Every row carries a `scope` (model, prompt, retrieval settings) and a `corpus` fingerprint (document count and
    highest document id). Uploading or deleting any document changes the corpus fingerprint, and changing the model,
    prompt, k, mode, threshold, reranker or document filter changes the scope, so stale answers simply stop matching.
  * The cache never raises: a database problem there falls back to answering normally.
"""
import hashlib
import logging
import json
import re
import time
from dataclasses import asdict

import psycopg
from psycopg.types.json import Jsonb

from app import config
from app.answering import SYSTEM_PROMPT, Answer, Citation, answer_question

log = logging.getLogger(__name__)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def normalize(question: str) -> str:
    return re.sub(r"\s+", " ", question).strip().lower().rstrip(" ?!.")


def corpus_fingerprint(conn: psycopg.Connection) -> str:
    count, max_id = conn.execute("SELECT count(*), coalesce(max(id), 0) FROM documents").fetchone()
    return f"{count}:{max_id}"  # ids are never reused, so any upload or delete changes this


def make_scope(provider, *, k, mode, min_score, file_types, document_ids, reranker) -> str:
    return _sha(json.dumps({
        "model": getattr(provider, "model", type(provider).__name__),
        "prompt": _sha(SYSTEM_PROMPT), "k": k, "mode": mode, "min_score": min_score,
        "file_types": sorted(file_types or []), "document_ids": sorted(document_ids or []),
        "reranker": getattr(reranker, "model_name", type(reranker).__name__) if reranker is not None else None,
        "rerank_pool": config.RERANK_POOL if reranker is not None else None,
    }, sort_keys=True))


def _to_answer(data: dict) -> Answer:
    data = dict(data)
    data["citations"] = [Citation(**c) for c in data.get("citations", [])]
    return Answer(**data)


def answer_with_cache(conn: psycopg.Connection, embedder, provider, question: str, *, k: int | None = None,
                      mode: str = "hybrid", min_score: float | None = None, file_types=None, document_ids=None,
                      reranker=None, enabled: bool | None = None, threshold: float | None = None) -> Answer:
    """Like answer_question, but serves repeated or near-duplicate questions from the cache."""
    enabled = config.CACHE_ENABLED if enabled is None else enabled
    threshold = config.SEMANTIC_CACHE_THRESHOLD if threshold is None else threshold
    kwargs = dict(k=k, mode=mode, min_score=min_score, file_types=file_types, document_ids=document_ids, reranker=reranker)
    if not enabled:
        return answer_question(conn, embedder, provider, question, **kwargs)

    t0 = time.perf_counter()
    scope = make_scope(provider, k=k or config.ANSWER_TOP_K, mode=mode,
                       min_score=config.MIN_VECTOR_SCORE if min_score is None else min_score,
                       file_types=file_types, document_ids=document_ids, reranker=reranker)
    qvec = None
    try:
        corpus = corpus_fingerprint(conn)
        key = _sha(normalize(question))
        hit = None
        row = conn.execute("SELECT id, answer FROM answer_cache WHERE scope=%s AND corpus=%s AND key_hash=%s",
                           (scope, corpus, key)).fetchone()
        if row:
            hit = (row[0], row[1], "exact")
        else:
            qvec = embedder.embed_query(question)
            row = conn.execute(
                """SELECT id, answer, 1 - (embedding <=> %(q)s::vector) AS sim FROM answer_cache
                   WHERE scope = %(s)s AND corpus = %(c)s ORDER BY embedding <=> %(q)s::vector LIMIT 1""",
                {"q": qvec, "s": scope, "c": corpus}).fetchone()
            if row and row[2] >= threshold:
                hit = (row[0], row[1], "semantic")
        if hit:
            conn.execute("UPDATE answer_cache SET hits = hits + 1, last_hit_at = now() WHERE id = %s", (hit[0],))
            conn.commit()
            a = _to_answer(hit[1])
            a.question = question
            a.cache = hit[2]
            a.prompt_tokens = a.completion_tokens = None  # no tokens were spent on this request
            a.latency_ms = (time.perf_counter() - t0) * 1000
            return a
    except psycopg.Error as exc:
        log.warning("answer cache lookup failed, answering without it: %s", exc)
        conn.rollback()
        corpus = None

    result = answer_question(conn, embedder, provider, question, **kwargs)

    if result.status == "answered" and corpus is not None:
        try:
            if qvec is None:
                qvec = embedder.embed_query(question)
            conn.execute("DELETE FROM answer_cache WHERE corpus <> %s", (corpus,))  # drop rows for older document sets
            conn.execute(
                """INSERT INTO answer_cache (scope, corpus, key_hash, embedding, answer) VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (scope, corpus, key_hash) DO UPDATE SET answer = EXCLUDED.answer, embedding = EXCLUDED.embedding""",
                (scope, corpus, key, qvec, Jsonb(asdict(result))))
            conn.commit()
        except psycopg.Error as exc:
            log.warning("answer cache store failed: %s", exc)
            conn.rollback()
    return result
