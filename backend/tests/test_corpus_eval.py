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


def test_other_documents_in_the_database_do_not_distort_the_eval(db_ready, tmp_path):
    import uuid

    from app.db import get_conn
    from app.ingest import ingest_document

    text = b"# Setup\nInstall the widget with the setup command.\n\n# Usage\nRun the widget daily.\n"
    (tmp_path / "a.md").write_text(text.decode())
    qf = tmp_path / "q.json"
    qf.write_text(json.dumps([{"id": "q1", "question": "install widget setup command", "source": "a.md",
                               "evidence": "Install the widget"}]))
    # An identical copy under another name (like an earlier manual upload) must not take the top-k slots.
    other = f"manualupload-{uuid.uuid4().hex[:6]}.md"
    ingest_document(get_conn, HashEmbedder(), other, text)
    try:
        r = corpus_eval.run(embedder=HashEmbedder(), save=False, corpus=tmp_path, questions_file=qf, k=1)
        assert r["other_documents_in_db"] >= 1
        assert r["modes"]["keyword"]["hit@1"] == 1.0 and r["modes"]["vector"]["hit@1"] == 1.0
    finally:
        with get_conn() as c:
            c.execute("DELETE FROM documents WHERE filename = %s", (other,))


def test_label_matching_any_vs_all_and_prefix():
    from app.retrieval import RetrievedChunk

    def hit(i, source, text):
        return RetrievedChunk(i, 1, i, "p-" + source, None, None, text, score=0.0)

    hits = [hit(1, "a.md", "alpha text"), hit(2, "b.md", "beta text"), hit(3, "a.md", "gamma")]
    tg = [{"source": "a.md", "quote": "alpha"}, {"source": "b.md", "quote": "beta"}]
    assert corpus_eval.first_hit_rank(hits, tg, "p-", "any") == 1
    assert corpus_eval.first_hit_rank(hits, tg, "p-", "all") == 2            # needs both sources covered
    assert corpus_eval.first_hit_rank(hits[:1], tg, "p-", "all") is None
    assert corpus_eval.first_hit_rank(hits, [{"source": "a.md", "quote": "delta"}], "p-") is None
    assert corpus_eval.targets_of({"source": "a.md", "evidence": "x"}) == [{"source": "a.md", "quote": "x"}]


def test_new_label_schema_and_kind_breakdown(db_ready, tmp_path):
    (tmp_path / "a.md").write_text("# Setup\nInstall the widget with the setup command.\n\n# Usage\nRun the widget daily.\n")
    qf = tmp_path / "q.json"
    qf.write_text(json.dumps([
        {"id": "x1", "question": "install widget setup command", "kind": "paraphrase",
         "targets": [{"source": "a.md", "quote": "Install the widget"}]},
        {"id": "x2", "question": "install and run the widget", "kind": "multi", "match": "all",
         "targets": [{"source": "a.md", "quote": "Install the widget"}, {"source": "a.md", "quote": "Run the widget daily"}]},
    ]))
    r = corpus_eval.run(embedder=HashEmbedder(), save=False, corpus=tmp_path, questions_file=qf)
    assert r["questions"] == 2 and r["unlabelable"] == []
    assert set(r["modes"]["keyword"]["by_kind"]) == {"paraphrase", "multi"}
