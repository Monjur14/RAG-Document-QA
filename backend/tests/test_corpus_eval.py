import json

from evals import corpus_eval
from tests.fakes import HashEmbedder, WordOverlapReranker


def test_corpus_eval_runs_and_reports_by_format(db_ready, tmp_path):
    (tmp_path / "a.md").write_text("# Setup\nInstall the widget with the setup command.\n\n# Usage\nRun the widget daily.\n")
    qs = [
        {"id": "q1", "question": "install widget setup command", "source": "a.md", "evidence": "Install the widget"},
        {"id": "q2", "question": "split quote", "source": "a.md", "evidence": "text that is nowhere in the file"},
    ]
    qf = tmp_path / "q.json"
    qf.write_text(json.dumps(qs))
    r = corpus_eval.run(embedder=HashEmbedder(), save=False, corpus=tmp_path, questions_file=qf)
    assert r["questions"] == 1 and r["unlabelable"] == ["q2"]
    assert set(r["modes"]) == {"vector", "keyword", "hybrid"}
    assert r["modes"]["keyword"]["by_format"]["md"]["n"] == 1
    assert r["modes"]["keyword"]["hit@5"] == 1.0


def test_corpus_eval_includes_rerank_variants(db_ready, tmp_path):
    (tmp_path / "a.md").write_text("# Setup\nInstall the widget with the setup command.\n\n# Usage\nRun the widget daily.\n")
    qf = tmp_path / "q.json"
    qf.write_text(json.dumps([{"id": "q1", "question": "install widget", "source": "a.md", "evidence": "Install the widget"}]))
    r = corpus_eval.run(embedder=HashEmbedder(), reranker=WordOverlapReranker(), save=False, corpus=tmp_path, questions_file=qf)
    assert {"vector+rerank", "hybrid+rerank"} <= set(r["modes"]) and r["reranker"] == "word-overlap"
