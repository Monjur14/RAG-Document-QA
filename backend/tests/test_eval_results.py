import json

from fastapi.testclient import TestClient

from app.eval_results import latest_results
from app.main import app


def write(d, name, data):
    (d / name).write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")


def test_picks_newest_file_of_each_kind_and_drops_rows(tmp_path):
    write(tmp_path, "corpus_20261001_100000.json", {"timestamp": "old"})
    write(tmp_path, "corpus_20261002_100000.json", {"timestamp": "new", "modes": {"hybrid": {"mrr": 0.8, "not_ranked_first": [1, 2]}}})
    write(tmp_path, "answers_20261002_100000.json", {"answerable": {"success": 0.9}, "answerable_rows": [{"id": "f01"}]})
    r = latest_results(tmp_path)
    assert r["retrieval"]["timestamp"] == "new" and r["retrieval"]["file"] == "corpus_20261002_100000.json"
    assert r["retrieval"]["modes"]["hybrid"] == {"mrr": 0.8}
    assert "answerable_rows" not in r["answers"]
    assert r["cache"] is None and r["threshold"] is None


def test_skips_corrupt_newest_file(tmp_path):
    write(tmp_path, "cache_20261001_100000.json", {"ok": True})
    write(tmp_path, "cache_20261002_100000.json", "{not json")
    assert latest_results(tmp_path)["cache"]["ok"] is True


def test_redteam_before_after_and_ablations(tmp_path):
    write(tmp_path, "redteam_naive_20261005_072504.json", {"label": "naive (no defenses)", "attack_success_rate": 0.475, "results": [1]})
    write(tmp_path, "redteam_current_20261005_072538.json", {"label": "current defenses", "attack_success_rate": 0.35})
    write(tmp_path, "redteam_current_20261005_080900.json", {"label": "current defenses", "attack_success_rate": 0.0})
    write(tmp_path, "redteam_current_20261005_080933.json", {"label": "layers: scan", "layers": ["scan"], "attack_success_rate": 0.225})
    write(tmp_path, "redteam_current_20261005_074145.json", {"label": "layers: none", "layers": [], "attack_success_rate": 0.35})
    rt = latest_results(tmp_path)["redteam"]
    assert rt["naive"]["attack_success_rate"] == 0.475 and "results" not in rt["naive"]
    assert rt["defended"]["attack_success_rate"] == 0.0   # the newest "current defenses" run wins
    assert [a["label"] for a in rt["ablations"]] == ["layers: none", "layers: scan"]


def test_missing_folder_gives_nulls(tmp_path):
    r = latest_results(tmp_path / "nope")
    assert r["answers"] is None and r["redteam"] == {"naive": None, "defended": None, "ablations": []}


def test_endpoint_reads_the_real_results_folder():
    r = TestClient(app).get("/evals/latest")
    assert r.status_code == 200
    assert set(r.json()) == {"retrieval", "answers", "cache", "threshold", "redteam"}
