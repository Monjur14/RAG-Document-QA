"""Per-request logging and the numbers behind the metrics page: cost, tokens, latency, cache hits, errors.

Nothing sensitive is logged: no question text, no answer text, only sizes, counts and timings.
"""
import psycopg

# USD per 1 million tokens: (input, output). Local models (Ollama) cost nothing, so unknown models are free.
# Hosted prices change often: check the provider's pricing page before trusting these.
PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
    "claude-haiku-4-5": (1.00, 5.00),
}


def estimate_cost(model: str | None, prompt_tokens: int | None, completion_tokens: int | None) -> float:
    price = PRICE_PER_MTOK.get(model or "")
    if not price:
        return 0.0
    return ((prompt_tokens or 0) * price[0] + (completion_tokens or 0) * price[1]) / 1_000_000


def log_request(conn: psycopg.Connection, *, question: str, status: str, latency_ms: float, cache: str = "miss",
                model: str | None = None, prompt_tokens: int | None = None, completion_tokens: int | None = None,
                retrieved: int | None = None, confidence: float | None = None, error: str | None = None) -> None:
    """Record one request. Never raises: a logging problem must not break answering."""
    try:
        cost = 0.0 if cache != "miss" else estimate_cost(model, prompt_tokens, completion_tokens)
        conn.execute(
            """INSERT INTO request_log (status, cache, model, prompt_tokens, completion_tokens, cost_usd,
                                        latency_ms, retrieved, confidence, question_chars, error)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (status, cache, model, prompt_tokens, completion_tokens, cost, latency_ms, retrieved, confidence,
             len(question), (error or None) and error[:200]),
        )
        conn.commit()
    except psycopg.Error:
        conn.rollback()


def summary(conn: psycopg.Connection, hours: float | None = None) -> dict:
    """Aggregate numbers over the last `hours` (all time when None)."""
    where, params = ("WHERE created_at >= now() - make_interval(secs => %s)", (hours * 3600,)) if hours else ("", ())
    row = conn.execute(
        f"""SELECT count(*),
                   count(*) FILTER (WHERE status = 'error'),
                   count(*) FILTER (WHERE cache <> 'miss'),
                   coalesce(sum(cost_usd), 0),
                   coalesce(sum(prompt_tokens), 0), coalesce(sum(completion_tokens), 0),
                   percentile_cont(0.5)  WITHIN GROUP (ORDER BY latency_ms),
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
            FROM request_log {where}""", params).fetchone()
    n, errors, hits, cost, p_tok, c_tok, p50, p95 = row
    by_status = dict(conn.execute(f"SELECT status, count(*) FROM request_log {where} GROUP BY status", params).fetchall())
    by_model = dict(conn.execute(
        f"SELECT model, count(*) FROM request_log {where + (' AND ' if where else 'WHERE ')} model IS NOT NULL GROUP BY model",
        params).fetchall())
    # Latency of requests that really called the LLM, so cache hits and early refusals don't hide model speed.
    llm = conn.execute(
        f"""SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms),
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
            FROM request_log {where + (' AND ' if where else 'WHERE ')} prompt_tokens IS NOT NULL AND cache = 'miss'""",
        params).fetchone()
    return {
        "requests": n,
        "error_rate": round(errors / n, 4) if n else 0.0,
        "cache_hit_rate": round(hits / n, 4) if n else 0.0,
        "total_cost_usd": float(cost),
        "avg_cost_usd": float(cost) / n if n else 0.0,
        "prompt_tokens": int(p_tok), "completion_tokens": int(c_tok),
        "latency_ms": {"p50": round(p50 or 0, 1), "p95": round(p95 or 0, 1)},
        "llm_latency_ms": {"p50": round(llm[0] or 0, 1), "p95": round(llm[1] or 0, 1)},
        "by_status": by_status,
        "by_model": by_model,   # which model answered: shows when fallback kicked in
    }
