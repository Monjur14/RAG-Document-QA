from app.rerank import rerank
from app.retrieval import RetrievedChunk, search
from tests.fakes import HashEmbedder, WordOverlapReranker


def _hit(i, text, vs=0.5):
    return RetrievedChunk(i, 1, i, "a.md", f"h{i}", None, text, score=0.1, vector_score=vs, vector_rank=i)


def test_rerank_orders_by_score_and_keeps_retrieval_fields():
    hits = [_hit(1, "unrelated words here"), _hit(2, "blue sky today"), _hit(3, "sky")]
    out = rerank("blue sky", hits, WordOverlapReranker(), k=2)
    assert [h.chunk_id for h in out] == [2, 3]
    assert out[0].rerank_score == out[0].score == 2.0
    assert out[0].vector_score == 0.5 and out[0].vector_rank == 2  # refusal threshold still has its input


def test_rerank_empty_and_ties_are_stable():
    assert rerank("q", [], WordOverlapReranker(), k=3) == []
    hits = [_hit(5, "x"), _hit(4, "x")]
    assert [h.chunk_id for h in rerank("q", hits, WordOverlapReranker(), k=2)] == [4, 5]


def test_search_with_reranker_returns_k_results(db_ready):
    import uuid

    from app.db import get_conn
    from app.ingest import ingest_document

    emb, name = HashEmbedder(), f"rr-{uuid.uuid4().hex[:6]}.md"
    ingest_document(get_conn, emb, name, b"# A\napples grow on trees.\n\n# B\nbananas are yellow fruit.\n\n# C\ncars drive fast.\n")
    try:
        with get_conn() as conn:
            hits = search(conn, emb, "yellow bananas", k=2, mode="hybrid", reranker=WordOverlapReranker())
            hits = [h for h in hits if h.source == name]
        assert hits and hits[0].heading == "B" and hits[0].rerank_score is not None
    finally:
        with get_conn() as c:
            c.execute("DELETE FROM documents WHERE filename = %s", (name,))
