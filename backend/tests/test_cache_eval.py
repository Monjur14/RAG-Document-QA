import json

from evals import cache_eval
from tests.fakes import FakeProvider, HashEmbedder

DOC = "# Setup\nInstall the widget with the setup command.\n\n# Usage\nRun the widget daily to keep it fresh.\n"


def _files(tmp_path):
    (tmp_path / "a.md").write_text(DOC)
    qf = tmp_path / "q.json"
    qf.write_text(json.dumps([
        {"id": "q1", "question": "How do I install the widget with the setup command?", "source": "a.md", "evidence": "Install the widget"},
        {"id": "q2", "question": "How often should I run the widget daily?", "source": "a.md", "evidence": "Run the widget daily"},
    ]))
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps({
        "positives": [{"id": "q1", "reworded": "setup command with the widget install I do how"}],      # same words, other order
        "negatives": [{"id": "q2", "question": "never remove the widget weekly"}],
    }))
    return qf, pf


def test_replay_saves_llm_calls_and_never_serves_near_misses(db_ready, tmp_path):
    qf, pf = _files(tmp_path)
    provider = FakeProvider("Install it [1].")
    r = cache_eval.run(embedder=HashEmbedder(), provider=provider, save=False, corpus=tmp_path,
                       questions_file=qf, pairs_file=pf, threshold=0.95)
    assert r["workload"] == {"questions": 1, "requests": 3}
    assert r["cache_off"]["llm_calls"] == 3 and r["cache_on"]["llm_calls"] == 1
    assert r["cache_on"]["exact_hits"] == 1 and r["cache_on"]["semantic_hits"] == 1
    assert r["savings"]["llm_calls"] == round(1 - 1 / 3, 3) and r["savings"]["prompt_tokens"] > 0.6
    assert r["rewordings_served_from_cache"] == 1
    assert r["wrong_hits_on_near_misses"] == []                 # different meaning: must not hit
    assert r["answer_still_supported"]["cache_on"]["reworded"] == 1.0


def test_similarity_table_orders_hits_by_threshold(db_ready, tmp_path):
    qf, pf = _files(tmp_path)
    questions = json.loads(qf.read_text())
    s = cache_eval.similarity_analysis(HashEmbedder(), questions, json.loads(pf.read_text()))
    hits = [row["rewordings_hit"] for row in s["by_threshold"]]
    assert hits == sorted(hits, reverse=True)                   # a stricter threshold never hits more
    assert s["rewording_sim"]["min"] > 0.9 and s["near_miss_sim"]["max"] < 0.5
    assert s["by_threshold"][-1]["near_misses_hit"] == 0


def test_a_too_loose_threshold_is_caught_as_a_wrong_hit(db_ready, tmp_path):
    qf, pf = _files(tmp_path)
    r = cache_eval.run(embedder=HashEmbedder(), provider=FakeProvider("Install it [1]."), save=False, corpus=tmp_path,
                       questions_file=qf, pairs_file=pf, threshold=-1.0)   # accepts anything
    assert len(r["wrong_hits_on_near_misses"]) == 1
