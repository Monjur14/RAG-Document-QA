"""Calibrate the "I don't know" threshold (MIN_VECTOR_SCORE) with retrieval only (no LLM needed).

    python -m evals.threshold_eval

For every answerable and unanswerable question we take the best cosine similarity retrieval finds.
If the two groups separate, a threshold between them refuses the unanswerable ones without
refusing answerable ones. "on-topic" unanswerable questions (about Orbit, but not covered by the
docs) score high and are NOT separable by a threshold; the LLM's own "I don't know" has to catch those.
This is a seed set; recalibrate on the full 80 + 20 question sets in Week 2.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

from app import config
from app.chunking import ChunkConfig
from app.db import get_conn, migrate
from app.embeddings import Embedder, get_embedder
from app.ingest import ingest_document
from app.retrieval import search

DATA = Path(__file__).parent / "data"
RESULTS = Path(__file__).parent / "results"


def best_score(hits, prefix: str) -> float:
    scores = [h.vector_score for h in hits if h.source.startswith(prefix) and h.vector_score is not None]
    return max(scores) if scores else 0.0


def evaluate(answerable: list[float], unanswerable: list[tuple[str, float]], threshold: float) -> dict:
    """Fraction of answerable questions kept and of unanswerable questions refused at `threshold`."""
    kept = sum(s >= threshold for s in answerable) / len(answerable)
    refused = {}
    for kind in ("off-topic", "on-topic"):
        scores = [s for k, s in unanswerable if k == kind]
        refused[kind] = sum(s < threshold for s in scores) / len(scores) if scores else None
    return {"threshold": threshold, "answerable_kept": kept, "refused": refused}


def run(embedder: Embedder | None = None, cfg: ChunkConfig | None = None, save: bool = True) -> dict:
    embedder = embedder or get_embedder()
    cfg = cfg or ChunkConfig()
    answerable_q = json.loads((DATA / "retrieval_questions.json").read_text(encoding="utf-8"))
    unanswerable_q = json.loads((DATA / "unanswerable_questions.json").read_text(encoding="utf-8"))
    prefix = f"evalset-{uuid.uuid4().hex[:6]}-"
    migrate()
    try:
        for f in sorted((DATA / "docs").glob("*.md")):
            ingest_document(get_conn, embedder, prefix + f.name, f.read_bytes(), cfg)
        with get_conn() as conn:
            def score(q: str) -> float:
                return best_score(search(conn, embedder, q, k=5, mode="hybrid"), prefix)

            ans = [(q["question"], score(q["question"])) for q in answerable_q]
            unans = [(q["question"], q["kind"], score(q["question"])) for q in unanswerable_q]
    finally:
        with get_conn() as c:
            c.execute("DELETE FROM documents WHERE filename LIKE %s", (prefix + "%",))

    a_scores = [s for _, s in ans]
    off = [s for _, k, s in unans if k == "off-topic"]
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "embedding_model": getattr(embedder, "model_name", type(embedder).__name__),
        "answerable": {"min": min(a_scores), "mean": sum(a_scores) / len(a_scores), "scores": sorted(ans, key=lambda x: x[1])[:5]},
        "unanswerable": [{"question": q, "kind": k, "score": s} for q, k, s in sorted(unans, key=lambda x: -x[2])],
        "separable_off_topic": bool(off) and max(off) < min(a_scores),
        "suggested_threshold": round((max(off) + min(a_scores)) / 2, 3) if off and max(off) < min(a_scores) else None,
        "at_configured_threshold": evaluate(a_scores, [(k, s) for _, k, s in unans], config.MIN_VECTOR_SCORE),
    }
    if save:
        RESULTS.mkdir(exist_ok=True)
        path = RESULTS / f"threshold_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["saved_to"] = str(path)
    return report


def print_report(r: dict) -> None:
    a = r["answerable"]
    print(f"\nmodel={r['embedding_model']}")
    print(f"answerable questions: lowest best-score {a['min']:.3f}, mean {a['mean']:.3f}")
    print("lowest answerable:")
    for q, s in a["scores"]:
        print(f"  {s:.3f}  {q}")
    print("unanswerable (best cosine similarity found):")
    for u in r["unanswerable"]:
        print(f"  {u['score']:.3f}  [{u['kind']}] {u['question']}")
    c = r["at_configured_threshold"]
    print(f"\nat MIN_VECTOR_SCORE={c['threshold']}: keeps {c['answerable_kept']:.0%} of answerable; "
          f"refuses {c['refused']['off-topic']:.0%} of off-topic and {c['refused']['on-topic']:.0%} of on-topic unanswerable")
    if r["suggested_threshold"] is not None:
        print(f"off-topic questions separate cleanly; a threshold near {r['suggested_threshold']} would refuse them all "
              f"without losing any answerable question")
    else:
        print("off-topic and answerable scores overlap: no clean threshold on this seed set")
    if "saved_to" in r:
        print(f"saved: {r['saved_to']}")


if __name__ == "__main__":
    print_report(run())
