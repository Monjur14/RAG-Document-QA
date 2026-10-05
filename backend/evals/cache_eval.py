"""Cache benchmark: how much does the answer cache save, and does the similarity threshold ever serve a wrong answer?

    python -m evals.cache_eval                  # real corpus, real LLM chain (see LLM_PROVIDERS), ~2-4 minutes
    python -m evals.cache_eval --no-rerank
    python -m evals.cache_eval --threshold 0.93

Part 1, similarity (no LLM): for each threshold, how many true rewordings would hit (good) and how many questions
that only look similar but mean something different would hit (bad: a wrong answer served from the cache).
Part 2, replay (real pipeline): each question is asked, repeated with different casing, then reworded. The same
workload runs with the cache off and on, and we compare latency, tokens, estimated cost, and whether the reused
answer still cites the right passage. Near-miss questions are then asked with the cache on: any hit is a wrong hit.
"""
import json
import statistics
import time
import uuid
from datetime import datetime
from pathlib import Path

from app import config
from app.cache import answer_with_cache
from app.chunking import ChunkConfig
from app.db import get_conn, migrate
from app.embeddings import Embedder, get_embedder
from app.ingest import ingest_document
from app.metrics import estimate_cost
from evals.answer_eval import citations_support
from evals.corpus_eval import CORPUS, DATA, QUESTION_FILES, RESULTS, load_questions, norm, targets_of

PAIRS_FILE = DATA / "cache_pairs.json"
THRESHOLDS = (0.80, 0.85, 0.90, 0.92, 0.94, 0.95, 0.97)
REFERENCE_PRICED_MODEL = "gpt-4o-mini"   # what the same tokens would cost on a hosted model (local models cost $0)


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))  # embeddings are L2-normalised, so this is the cosine similarity


def similarity_analysis(embedder: Embedder, questions: list[dict], pairs: dict, thresholds=THRESHOLDS) -> dict:
    by_id = {q["id"]: q for q in questions}
    pos = [(p["id"], p["reworded"]) for p in pairs["positives"] if p["id"] in by_id]
    neg = [(n["id"], n["question"]) for n in pairs["negatives"] if n["id"] in by_id]
    base = {q["id"]: embedder.embed_query(q["question"]) for q in questions}
    pos_sims = [_dot(base[i], embedder.embed_query(t)) for i, t in pos]
    neg_sims = [_dot(base[i], embedder.embed_query(t)) for i, t in neg]
    # Natural near-misses: each question against every other question in the set (all ask different things).
    ids = list(base)
    other = [max(_dot(base[a], base[b]) for b in ids if b != a) for a in ids]
    table = [{
        "threshold": t,
        "rewordings_hit": round(sum(s >= t for s in pos_sims) / len(pos_sims), 3) if pos_sims else 0.0,
        "near_misses_hit": sum(s >= t for s in neg_sims),
        "other_questions_hit": sum(s >= t for s in other),
    } for t in thresholds]
    return {
        "n_rewordings": len(pos_sims), "n_near_misses": len(neg_sims), "n_other_questions": len(other),
        "rewording_sim": {"min": round(min(pos_sims), 3), "median": round(statistics.median(pos_sims), 3)} if pos_sims else {},
        "near_miss_sim": {"max": round(max(neg_sims), 3), "median": round(statistics.median(neg_sims), 3)} if neg_sims else {},
        "other_question_sim_max": round(max(other), 3) if other else None,
        "by_threshold": table,
    }


def _pctl(values: list[float], q: float) -> float:
    s = sorted(values)
    return round(s[min(len(s) - 1, int(len(s) * q))], 1) if s else 0.0


def _stats(rows: list[dict]) -> dict:
    lat = [r["latency_ms"] for r in rows]
    p_tok = sum(r["prompt_tokens"] or 0 for r in rows)
    c_tok = sum(r["completion_tokens"] or 0 for r in rows)
    return {
        "requests": len(rows),
        "llm_calls": sum(r["prompt_tokens"] is not None for r in rows),
        "exact_hits": sum(r["cache"] == "exact" for r in rows),
        "semantic_hits": sum(r["cache"] == "semantic" for r in rows),
        "avg_latency_ms": round(statistics.fmean(lat), 1) if lat else 0.0,
        "p50_ms": _pctl(lat, 0.5), "p95_ms": _pctl(lat, 0.95),
        "prompt_tokens": p_tok, "completion_tokens": c_tok,
        "est_cost_usd_if_hosted": round(estimate_cost(REFERENCE_PRICED_MODEL, p_tok, c_tok), 6),
    }


def _case_variant(text: str) -> str:
    return "  " + text.upper().rstrip("?.! ") + " "   # same question, different casing, spacing and punctuation


def run(embedder: Embedder | None = None, provider=None, reranker=None, threshold: float | None = None, save: bool = True,
        corpus: Path = CORPUS, questions_file=None, pairs_file: Path = PAIRS_FILE) -> dict:
    files = sorted(p for p in corpus.glob("*") if p.suffix.lower() in {".md", ".pdf", ".docx", ".html", ".txt"})
    if not files:
        raise SystemExit(f"No corpus files in {corpus}. Run: python -m evals.fetch_corpus")
    embedder = embedder or get_embedder()
    if provider is None:
        from app.providers import get_provider

        provider = get_provider()
    threshold = config.SEMANTIC_CACHE_THRESHOLD if threshold is None else threshold
    questions = load_questions(questions_file or QUESTION_FILES)
    pairs = json.loads(Path(pairs_file).read_text(encoding="utf-8"))
    by_id = {q["id"]: q for q in questions}
    prefix = f"cache-{uuid.uuid4().hex[:6]}-"
    migrate()

    report: dict = {"timestamp": datetime.now().isoformat(timespec="seconds"), "threshold": threshold,
                    "reranker": getattr(reranker, "model_name", type(reranker).__name__) if reranker else None,
                    "similarity": similarity_analysis(embedder, questions, pairs)}
    try:
        doc_ids = [ingest_document(get_conn, embedder, prefix + f.name, f.read_bytes(), ChunkConfig()).document_id for f in files]
        usable = [p for p in pairs["positives"] if p["id"] in by_id]
        workload: list[tuple[str, str, str]] = []   # (kind, question text, original id)
        for p in usable:
            q = by_id[p["id"]]
            workload += [("original", q["question"], q["id"]), ("repeat", _case_variant(q["question"]), q["id"]),
                         ("reworded", p["reworded"], q["id"])]

        def replay(enabled: bool) -> list[dict]:
            rows = []
            with get_conn() as conn:
                conn.execute("DELETE FROM answer_cache")
                conn.commit()
                for kind, text, qid in workload:
                    tg = [{**t, "source": t["source"]} for t in targets_of(by_id[qid])]
                    t0 = time.perf_counter()
                    a = answer_with_cache(conn, embedder, provider, text, document_ids=doc_ids, reranker=reranker,
                                          enabled=enabled, threshold=threshold)
                    rows.append({
                        "kind": kind, "id": qid, "cache": a.cache, "status": a.status, "model": a.model,
                        "latency_ms": (time.perf_counter() - t0) * 1000,
                        "prompt_tokens": a.prompt_tokens, "completion_tokens": a.completion_tokens,
                        "supported": a.status == "answered" and citations_support(a.citations, tg, prefix, by_id[qid].get("match", "any")),
                    })
            return rows

        off, on = replay(False), replay(True)

        wrong_hits = []
        with get_conn() as conn:
            for n in pairs["negatives"]:
                if n["id"] not in by_id:
                    continue
                # Prime the cache with the original, then ask the near-miss: any hit is a wrong answer served.
                answer_with_cache(conn, embedder, provider, by_id[n["id"]]["question"], document_ids=doc_ids,
                                  reranker=reranker, threshold=threshold)
                a = answer_with_cache(conn, embedder, provider, n["question"], document_ids=doc_ids,
                                      reranker=reranker, threshold=threshold)
                if a.cache != "miss":
                    wrong_hits.append({"original": by_id[n["id"]]["question"], "asked": n["question"], "cache": a.cache})
            conn.execute("DELETE FROM answer_cache")
            conn.commit()

        def success(rows, kind):
            sub = [r for r in rows if r["kind"] == kind]
            return round(sum(r["supported"] for r in sub) / len(sub), 3) if sub else 0.0

        base, cached = _stats(off), _stats(on)
        saved = lambda k: (round(1 - cached[k] / base[k], 3) if base[k] else 0.0)  # noqa: E731
        report.update({
            "model": next((r["model"] for r in off if r["model"]), None),
            "workload": {"questions": len(usable), "requests": len(workload)},
            "cache_off": base, "cache_on": cached,
            "savings": {"latency_avg": saved("avg_latency_ms"), "prompt_tokens": saved("prompt_tokens"),
                        "completion_tokens": saved("completion_tokens"), "cost": saved("est_cost_usd_if_hosted"),
                        "llm_calls": saved("llm_calls")},
            "answer_still_supported": {"cache_off": {k: success(off, k) for k in ("original", "repeat", "reworded")},
                                       "cache_on": {k: success(on, k) for k in ("original", "repeat", "reworded")}},
            "rewordings_served_from_cache": sum(r["cache"] == "semantic" for r in on if r["kind"] == "reworded"),
            "wrong_hits_on_near_misses": wrong_hits,
        })
    finally:
        with get_conn() as c:
            c.execute("DELETE FROM documents WHERE filename LIKE %s", (prefix + "%",))
            c.execute("DELETE FROM answer_cache")

    if save:
        RESULTS.mkdir(exist_ok=True)
        path = RESULTS / f"cache_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["saved_to"] = str(path)
    return report


def print_report(r: dict) -> None:
    s = r["similarity"]
    print(f"\ncache threshold in use: {r['threshold']}   model: {r.get('model')}   reranker: {r['reranker']}")
    print(f"\nPART 1: similarity  ({s['n_rewordings']} rewordings, {s['n_near_misses']} near-miss questions, "
          f"{s['n_other_questions']} other questions)")
    print(f"  reworded questions: similarity min {s['rewording_sim'].get('min')}, median {s['rewording_sim'].get('median')}")
    print(f"  near-miss questions (different meaning): similarity max {s['near_miss_sim'].get('max')}, median {s['near_miss_sim'].get('median')}")
    print(f"  most similar pair among all other questions: {s['other_question_sim_max']}")
    print(f"  {'threshold':>9}  {'rewordings that hit':>20}  {'near-misses that hit (bad)':>27}  {'other questions that hit (bad)':>31}")
    for row in s["by_threshold"]:
        print(f"  {row['threshold']:>9.2f}  {row['rewordings_hit']:>20.2f}  {row['near_misses_hit']:>27}  {row['other_questions_hit']:>31}")
    print(f"\nPART 2: replay of {r['workload']['requests']} requests ({r['workload']['questions']} questions: asked, repeated, reworded)")
    print(f"  {'':<22}{'cache off':>12}{'cache on':>12}{'saved':>9}")
    off, on, sv = r["cache_off"], r["cache_on"], r["savings"]
    print(f"  {'LLM calls':<22}{off['llm_calls']:>12}{on['llm_calls']:>12}{sv['llm_calls']:>9.0%}")
    print(f"  {'avg latency (ms)':<22}{off['avg_latency_ms']:>12}{on['avg_latency_ms']:>12}{sv['latency_avg']:>9.0%}")
    print(f"  {'p50 / p95 (ms)':<22}{str(off['p50_ms']) + ' / ' + str(off['p95_ms']):>12}{str(on['p50_ms']) + ' / ' + str(on['p95_ms']):>12}")
    print(f"  {'prompt tokens':<22}{off['prompt_tokens']:>12}{on['prompt_tokens']:>12}{sv['prompt_tokens']:>9.0%}")
    print(f"  {'completion tokens':<22}{off['completion_tokens']:>12}{on['completion_tokens']:>12}{sv['completion_tokens']:>9.0%}")
    print(f"  {'cost if hosted (USD)':<22}{off['est_cost_usd_if_hosted']:>12}{on['est_cost_usd_if_hosted']:>12}{sv['cost']:>9.0%}"
          f"   (priced as {REFERENCE_PRICED_MODEL}; your local model really costs $0)")
    print(f"  hits: {on['exact_hits']} exact, {on['semantic_hits']} semantic;  rewordings served from cache: {r['rewordings_served_from_cache']}")
    sup = r["answer_still_supported"]
    print(f"  cited passage has the quote  (original / repeat / reworded):  off {sup['cache_off']['original']:.2f}/"
          f"{sup['cache_off']['repeat']:.2f}/{sup['cache_off']['reworded']:.2f}   on {sup['cache_on']['original']:.2f}/"
          f"{sup['cache_on']['repeat']:.2f}/{sup['cache_on']['reworded']:.2f}")
    print(f"\n  wrong hits on near-miss questions: {len(r['wrong_hits_on_near_misses'])}")
    for w in r["wrong_hits_on_near_misses"]:
        print(f"    asked {w['asked']!r} but got the cached answer to {w['original']!r} ({w['cache']})")
    if "saved_to" in r:
        print(f"\nsaved: {r['saved_to']}")


if __name__ == "__main__":
    import sys

    rr = None
    if "--no-rerank" not in sys.argv:
        from app.rerank import get_reranker

        rr = get_reranker()
    th = float(sys.argv[sys.argv.index("--threshold") + 1]) if "--threshold" in sys.argv else None
    print_report(run(reranker=rr, threshold=th))
