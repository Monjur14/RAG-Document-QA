import uuid

import pytest

from app.db import get_conn
from app.ingest import ingest_document
from app.retrieval import RetrievedChunk, keyword_search, rrf_merge, search, vector_search
from tests.fakes import HashEmbedder

EMB = HashEmbedder()


def chunk(i: int, score: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(i, 1, i, "a.md", None, None, f"t{i}", score)


# ---- pure: no database ----
def test_rrf_item_in_both_lists_beats_item_in_one():
    merged = rrf_merge([chunk(1), chunk(2)], [chunk(3), chunk(2)])
    assert merged[0].chunk_id == 2
    assert (merged[0].vector_rank, merged[0].keyword_rank) == (2, 2)
    assert {m.chunk_id for m in merged} == {1, 2, 3}


def test_rrf_handles_empty_lists():
    assert rrf_merge([], []) == []
    assert [m.chunk_id for m in rrf_merge([chunk(1)], [])] == [1]


# ---- database ----
@pytest.fixture()
def docs(db_ready):
    prefix = f"rtest-{uuid.uuid4().hex[:8]}"
    a = ingest_document(
        get_conn, EMB, f"{prefix}-a.md",
        b"# Cats\nCats are small carnivorous mammals that purr loudly.\n\n"
        b"# Databases\nPostgreSQL is a relational database with vector search through pgvector.\n",
    )
    b = ingest_document(get_conn, EMB, f"{prefix}-b.txt", b"Bananas are yellow fruit rich in potassium.")
    yield a.document_id, b.document_id
    with get_conn() as c:
        c.execute("DELETE FROM documents WHERE filename LIKE %s", (f"{prefix}%",))


def _search(mode, query, ids, **kw):
    with get_conn() as c:
        return search(c, EMB, query, mode=mode, document_ids=list(ids), **kw)


def test_vector_search_finds_semantically_closest_chunk(docs):
    hits = _search("vector", "database vector search", docs)
    assert hits[0].heading == "Databases"
    assert hits[0].vector_score > hits[-1].vector_score
    assert hits[0].vector_rank == 1 and hits[0].keyword_rank is None


def test_keyword_search_exact_term_and_or_semantics(docs):
    assert _search("keyword", "pgvector", docs)[0].heading == "Databases"
    texts = " ".join(h.text for h in _search("keyword", "purr potassium", docs))
    assert "purr" in texts and "potassium" in texts  # OR, not AND


def test_keyword_search_stopword_only_or_symbols_returns_nothing(docs):
    assert _search("keyword", "the of and", docs) == []
    assert _search("keyword", "?!", docs) == []


def test_keyword_search_is_injection_safe(docs):
    assert _search("keyword", "cats'); DROP TABLE chunks; --", docs)  # treated as plain words
    with get_conn() as c:
        assert c.execute("SELECT count(*) FROM chunks").fetchone()[0] > 0


def test_hybrid_combines_both_signals(docs):
    hits = _search("hybrid", "postgresql vector search", docs)
    top = hits[0]
    assert top.heading == "Databases" and top.vector_rank == 1 and top.keyword_rank == 1


def test_k_limits_results(docs):
    assert len(_search("hybrid", "cats databases bananas", docs, k=2)) == 2


def test_filters_by_file_type_and_document(docs):
    a_id, b_id = docs
    with get_conn() as c:
        txt = search(c, EMB, "fruit", mode="vector", document_ids=[a_id, b_id], file_types=["txt"])
        only_a = search(c, EMB, "fruit", mode="vector", document_ids=[a_id])
    assert {h.document_id for h in txt} == {b_id}
    assert {h.document_id for h in only_a} == {a_id}


def test_unknown_mode_rejected(docs):
    with get_conn() as c, pytest.raises(ValueError):
        search(c, EMB, "x", mode="magic")


def test_failed_documents_are_not_searchable(docs):
    a_id, _ = docs
    with get_conn() as c:
        c.execute("UPDATE documents SET status = 'failed' WHERE id = %s", (a_id,))
        c.commit()
        assert search(c, EMB, "cats", mode="keyword", document_ids=[a_id]) == []
