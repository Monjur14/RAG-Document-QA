from app.retrieval import RetrievedChunk
from evals.threshold_eval import best_score, evaluate


def h(source, vs):
    return RetrievedChunk(1, 1, 0, source, None, None, "t", 0.0, vector_score=vs)


def test_best_score_only_counts_eval_documents():
    hits = [h("other.md", 0.99), h("evalset-x-a.md", 0.4), h("evalset-x-b.md", 0.6), h("evalset-x-c.md", None)]
    assert best_score(hits, "evalset-x-") == 0.6
    assert best_score([], "evalset-x-") == 0.0


def test_evaluate_counts_kept_and_refused():
    r = evaluate([0.6, 0.7, 0.4], [("off-topic", 0.2), ("off-topic", 0.55), ("on-topic", 0.65)], 0.5)
    assert round(r["answerable_kept"], 3) == round(2 / 3, 3)
    assert r["refused"] == {"off-topic": 0.5, "on-topic": 0.0}
