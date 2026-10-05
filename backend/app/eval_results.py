"""Read the newest saved eval result of each kind, for the read-only metrics page.

Only files in one fixed folder, with names from a fixed list of prefixes, are ever opened: nothing from the
request decides which file is read. Per-question rows are dropped so the response stays small.
"""
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "evals" / "results"

# kind shown on the page -> file name prefix written by the eval scripts
KINDS = {
    "retrieval": "corpus_",      # corpus_eval: hit@k and MRR per retrieval mode and format
    "answers": "answers_",       # answer_eval: answer success, citations, refusals
    "cache": "cache_",           # cache_eval: cost and latency with and without the cache
    "threshold": "threshold_",   # threshold_eval: the "I don't know" cut-off
}

# Large per-question lists the page never shows.
_DROP = {"answerable_rows", "unanswerable_rows", "results", "not_ranked_first", "unlabelable"}


def _trim(obj):
    if isinstance(obj, dict):
        return {k: _trim(v) for k, v in obj.items() if k not in _DROP}
    if isinstance(obj, list):
        return [_trim(v) for v in obj]
    return obj


def _load(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # a half-written or corrupt file is skipped, not fatal
    if not isinstance(data, dict):
        return None
    data = _trim(data)
    data["file"] = path.name
    return data


def _files(results_dir: Path, prefix: str) -> list[Path]:
    # File names end in _YYYYMMDD_HHMMSS.json, so sorting by name sorts by time. Newest first.
    return sorted(results_dir.glob(f"{prefix}*.json"), key=lambda p: p.name, reverse=True)


def _newest(results_dir: Path, prefix: str) -> dict | None:
    for path in _files(results_dir, prefix):
        if (data := _load(path)) is not None:
            return data
    return None


def _redteam(results_dir: Path) -> dict:
    """Before (no defenses), after (all defenses) and the newest run of each single-layer ablation."""
    naive = _newest(results_dir, "redteam_naive_")
    defended, layers = None, {}
    for path in _files(results_dir, "redteam_current_"):
        data = _load(path)
        if data is None:
            continue
        label = data.get("label", "")
        if label == "current defenses":
            defended = defended or data
        elif label.startswith("layers:") and label not in layers:
            layers[label] = data
    ablations = [
        {"label": label, "layers": d.get("layers", []), "attack_success_rate": d.get("attack_success_rate"),
         "cases": d.get("cases"), "timestamp": d.get("timestamp")}
        for label, d in sorted(layers.items())
    ]
    return {"naive": naive, "defended": defended, "ablations": ablations}


def latest_results(results_dir: Path = RESULTS_DIR) -> dict:
    out: dict = {kind: _newest(results_dir, prefix) for kind, prefix in KINDS.items()}
    out["redteam"] = _redteam(results_dir)
    return out
