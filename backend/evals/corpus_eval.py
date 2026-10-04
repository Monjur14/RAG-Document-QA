"""Retrieval eval on the real public corpus (FastAPI docs + NIST PDFs).

    python -m evals.fetch_corpus      # once, downloads the documents
    python -m evals.corpus_eval

A question is labeled with the source file and an exact quote (`evidence`) that answers it. A
retrieved chunk is a hit when it comes from that file and contains the quote (whitespace-normalized).
Results are broken down by file format. Labels whose quote no chunk contains (e.g. split across a
chunk boundary) are reported as `unlabelable` and excluded, instead of silently counting as misses.
"""
import json
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.chunking import ChunkConfig
from app.config import EMBEDDING_MODEL
from app.db import get_conn, migrate
from app.embeddings import Embedder, get_embedder
from app.ingest import ingest_document
from app.retrieval import search
from evals.retrieval_eval import CUTOFFS, MODES, summarize

DATA = Path(__file__).parent / "data"
CORPUS = DATA / "corpus"
RESULTS = Path(__file__).parent / "results"


def norm(text: str) -> str:
    return " ".join(text.split())


def first_hit_rank(hits, source: str, evidence: str) -> int | None:
    ev = norm(evidence)
    for i, h in enumerate(hits, 1):
        if h.source == source and ev in norm(h.text):
            return i
    return None


def run(embedder: Embedder | None = None, reranker=None, k: int = 5, cfg: ChunkConfig | None = None, save: bool = True,
        corpus: Path = CORPUS, questions_file: Path = DATA / "corpus_questions.json") -> dict:
    files = sorted(p for p in corpus.glob("*") if p.suffix.lower() in {".md", ".pdf", ".docx", ".html", ".txt"})
    if not files:
        raise SystemExit(f"No corpus files in {corpus}. Run: python -m evals.fetch_corpus")
    embedder = embedder or get_embedder()
    cfg = cfg or ChunkConfig()
    questions = json.loads(questions_file.read_text(encoding="utf-8"))
    prefix = f"corpus-{uuid.uuid4().hex[:6]}-"
    migrate()

    try:
        for f in files:
            ingest_document(get_conn, embedder, prefix + f.name, f.read_bytes(), cfg)

        with get_conn() as conn:
            # Drop labels no single chunk contains.
            usable, unlabelable = [], []
            chunk_text: dict[str, str] = {}
            for src, text in conn.execute("SELECT source, text FROM chunks WHERE source LIKE %s", (prefix + "%",)):
                chunk_text.setdefault(src, "")
                chunk_text[src] += "\n" + norm(text)
            for q in questions:
                ok = any(norm(q["evidence"]) in norm(t) for t in chunk_text.get(prefix + q["source"], "").split("\n"))
                (usable if ok else unlabelable).append(q)

            report = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "embedding_model": getattr(embedder, "model_name", type(embedder).__name__),
                "chunking": cfg.model_dump(),
                "k": k,
                "documents": [f.name for f in files],
                "questions": len(usable),
                "unlabelable": [q["id"] for q in unlabelable],
                "modes": {},
            }
            variants = [(m, m, None) for m in MODES]
            if reranker is not None:
                variants += [(f"{m}+rerank", m, reranker) for m in ("vector", "hybrid")]
            report["reranker"] = getattr(reranker, "model_name", type(reranker).__name__) if reranker else None
            for name, mode, rr in variants:
                ranks, by_fmt, misses, t0 = [], {}, [], time.perf_counter()
                for q in usable:
                    hits = [h for h in search(conn, embedder, q["question"], k=k, mode=mode, reranker=rr)
                            if h.source.startswith(prefix)]
                    rank = first_hit_rank(hits, prefix + q["source"], q["evidence"])
                    ranks.append(rank)
                    by_fmt.setdefault(Path(q["source"]).suffix.lstrip("."), []).append(rank)
                    if rank is None or rank > 1:
                        misses.append({"id": q["id"], "question": q["question"], "rank": rank,
                                       "expected": f"{q['source']} / {q.get('heading')}",
                                       "got": [f"{h.source[len(prefix):]} / {h.heading}" for h in hits[:3]]})
                ms = (time.perf_counter() - t0) * 1000 / len(usable)
                report["modes"][name] = {
                    **summarize(ranks),
                    "avg_ms_per_query": round(ms, 1),
                    "by_format": {fmt: {**summarize(r), "n": len(r)} for fmt, r in by_fmt.items()},
                    "not_ranked_first": misses,
                }
    finally:
        with get_conn() as c:
            c.execute("DELETE FROM documents WHERE filename LIKE %s", (prefix + "%",))

    if save:
        RESULTS.mkdir(exist_ok=True)
        path = RESULTS / f"corpus_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["saved_to"] = str(path)
    return report


def print_report(r: dict) -> None:
    print(f"\nmodel={r['embedding_model']}  chunking={r['chunking']['strategy']}/{r['chunking']['chunk_size']}  "
          f"questions={r['questions']}  k={r['k']}  docs={len(r['documents'])}")
    if r["unlabelable"]:
        print(f"excluded (quote split across chunks): {r['unlabelable']}")
    print(f"{'mode':<14}{'hit@1':>7}{'hit@3':>7}{'hit@5':>7}{'MRR':>8}{'ms/query':>10}")
    for mode, m in r["modes"].items():
        print(f"{mode:<14}{m['hit@1']:>7.2f}{m['hit@3']:>7.2f}{m['hit@5']:>7.2f}{m['mrr']:>8.3f}{m['avg_ms_per_query']:>10.1f}")
    print("\nby format (hit@1 / hit@5 / n):")
    for mode, m in r["modes"].items():
        parts = [f"{fmt}: {v['hit@1']:.2f}/{v['hit@5']:.2f}/{v['n']}" for fmt, v in m["by_format"].items()]
        print(f"  {mode:<13}" + "   ".join(parts))
    for mode, m in r["modes"].items():
        for miss in m["not_ranked_first"]:
            print(f"  [{mode}] {miss['id']} rank={miss['rank']} expected {miss['expected']} got {miss['got']}")
    if "saved_to" in r:
        print(f"\nsaved: {r['saved_to']}")


if __name__ == "__main__":
    import sys

    rr = None
    if "--no-rerank" not in sys.argv:
        from app.rerank import get_reranker

        rr = get_reranker()
    print_report(run(reranker=rr))
