"""Seed retrieval eval: vector vs keyword vs hybrid on a small labeled set.

    python -m evals.retrieval_eval

Each question is labeled with the one (file, heading) that answers it. A result is a hit when a
retrieved chunk comes from that file and heading. This is a 16-question *seed* set to prove the
harness; the full 80-question set is built in Week 2. Results are saved to evals/results/.
"""
import json
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.chunking import ChunkConfig
from app.db import get_conn, migrate
from app.embeddings import Embedder, get_embedder
from app.ingest import ingest_document
from app.retrieval import search

DATA = Path(__file__).parent / "data"
RESULTS = Path(__file__).parent / "results"
MODES = ["vector", "keyword", "hybrid"]
CUTOFFS = (1, 3, 5)


def first_hit_rank(hits, source: str, heading: str) -> int | None:
    """1-based rank of the first retrieved chunk that is the labeled passage, else None."""
    for i, h in enumerate(hits, 1):
        if h.source == source and h.heading == heading:
            return i
    return None


def summarize(ranks: list[int | None]) -> dict:
    n = len(ranks)
    out = {f"hit@{c}": sum(1 for r in ranks if r is not None and r <= c) / n for c in CUTOFFS}
    out["mrr"] = sum(1 / r for r in ranks if r) / n
    return out


def run(embedder: Embedder | None = None, k: int = 5, cfg: ChunkConfig | None = None, save: bool = True) -> dict:
    embedder = embedder or get_embedder()
    cfg = cfg or ChunkConfig()
    questions = json.loads((DATA / "retrieval_questions.json").read_text(encoding="utf-8"))
    prefix = f"evalset-{uuid.uuid4().hex[:6]}-"
    migrate()

    try:
        for f in sorted((DATA / "docs").glob("*.md")):
            ingest_document(get_conn, embedder, prefix + f.name, f.read_bytes(), cfg)

        report = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "embedding_model": getattr(embedder, "model_name", type(embedder).__name__),
            "chunking": cfg.model_dump(),
            "k": k,
            "questions": len(questions),
            "modes": {},
        }
        with get_conn() as conn:
            for mode in MODES:
                ranks, misses, t0 = [], [], time.perf_counter()
                for q in questions:
                    hits = search(conn, embedder, q["question"], k=k, mode=mode)
                    hits = [h for h in hits if h.source.startswith(prefix)]
                    rank = first_hit_rank(hits, prefix + q["source"], q["heading"])
                    ranks.append(rank)
                    if rank is None or rank > 1:
                        misses.append({"question": q["question"], "expected": q["heading"], "rank": rank,
                                       "got": [h.heading for h in hits[:3]]})
                ms = (time.perf_counter() - t0) * 1000 / len(questions)
                report["modes"][mode] = {**summarize(ranks), "avg_ms_per_query": round(ms, 1), "not_ranked_first": misses}
    finally:
        with get_conn() as c:
            c.execute("DELETE FROM documents WHERE filename LIKE %s", (prefix + "%",))

    if save:
        RESULTS.mkdir(exist_ok=True)
        path = RESULTS / f"retrieval_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["saved_to"] = str(path)
    return report


def print_report(r: dict) -> None:
    print(f"\nmodel={r['embedding_model']}  chunking={r['chunking']['strategy']}/{r['chunking']['chunk_size']}  "
          f"questions={r['questions']}  k={r['k']}")
    print(f"{'mode':<9}{'hit@1':>7}{'hit@3':>7}{'hit@5':>7}{'MRR':>8}{'ms/query':>10}")
    for mode, m in r["modes"].items():
        print(f"{mode:<9}{m['hit@1']:>7.2f}{m['hit@3']:>7.2f}{m['hit@5']:>7.2f}{m['mrr']:>8.3f}{m['avg_ms_per_query']:>10.1f}")
    for mode, m in r["modes"].items():
        for miss in m["not_ranked_first"]:
            print(f"  [{mode}] rank={miss['rank']} expected '{miss['expected']}' got {miss['got']} for: {miss['question']}")
    if "saved_to" in r:
        print(f"\nsaved: {r['saved_to']}")


if __name__ == "__main__":
    print_report(run())
