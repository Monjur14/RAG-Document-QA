from app.retrieval import RetrievedChunk
from evals.retrieval_eval import first_hit_rank, summarize


def h(source, heading):
    return RetrievedChunk(1, 1, 0, source, heading, None, "t", 0.0)


def test_first_hit_rank():
    hits = [h("a.md", "X"), h("a.md", "Y"), h("b.md", "Y")]
    assert first_hit_rank(hits, "a.md", "Y") == 2
    assert first_hit_rank(hits, "b.md", "Y") == 3
    assert first_hit_rank(hits, "a.md", "Z") is None


def test_summarize():
    s = summarize([1, 2, None, 5])
    assert s["hit@1"] == 0.25 and s["hit@3"] == 0.5 and s["hit@5"] == 0.75
    assert round(s["mrr"], 4) == round((1 + 0.5 + 0 + 0.2) / 4, 4)
