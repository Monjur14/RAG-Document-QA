import pytest
from fastapi.testclient import TestClient

from app import main
from app.db import get_conn
from app.main import app, embedder_dep, provider_dep, reranker_dep
from app.metrics import estimate_cost, log_request, summary
from app.providers import ProviderError
from tests.fakes import FakeProvider, HashEmbedder


def test_estimate_cost_local_is_free_and_hosted_uses_price_table():
    assert estimate_cost("llama3.1:8b", 1000, 100) == 0.0
    assert estimate_cost(None, 1, 1) == 0.0
    assert estimate_cost("gemini-2.0-flash", 1_000_000, 1_000_000) == pytest.approx(0.50)


@pytest.fixture()
def conn(db_ready):
    c = get_conn()
    c.execute("DELETE FROM request_log")
    c.commit()
    yield c
    c.execute("DELETE FROM request_log")
    c.commit()
    c.close()


def test_summary_percentiles_cache_errors_and_cost(conn):
    for ms in (100, 200, 300, 400):
        log_request(conn, question="q", status="answered", latency_ms=ms, model="gemini-2.0-flash",
                    prompt_tokens=1000, completion_tokens=100)
    log_request(conn, question="q", status="answered", latency_ms=5, cache="exact", model="gemini-2.0-flash",
                prompt_tokens=1000, completion_tokens=100)          # a cache hit costs nothing
    log_request(conn, question="q", status="error", latency_ms=50, error="ProviderError")
    s = summary(conn)
    assert s["requests"] == 6 and s["by_status"] == {"answered": 5, "error": 1}
    assert s["cache_hit_rate"] == pytest.approx(1 / 6, abs=1e-3) and s["error_rate"] == pytest.approx(1 / 6, abs=1e-3)
    assert s["total_cost_usd"] == pytest.approx(4 * (1000 * 0.10 + 100 * 0.40) / 1e6)
    assert s["llm_latency_ms"]["p50"] == 250.0              # only the 4 real LLM calls
    assert s["latency_ms"]["p95"] > s["latency_ms"]["p50"]


def test_summary_of_empty_log_and_time_window(conn):
    assert summary(conn)["requests"] == 0 and summary(conn, hours=1)["latency_ms"] == {"p50": 0, "p95": 0}
    log_request(conn, question="q", status="answered", latency_ms=10)
    conn.execute("UPDATE request_log SET created_at = now() - interval '3 hours'")
    conn.commit()
    assert summary(conn, hours=1)["requests"] == 0 and summary(conn)["requests"] == 1


def test_question_text_is_never_stored(conn):
    log_request(conn, question="my secret question", status="answered", latency_ms=1)
    cols = [r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name='request_log'")]
    assert not {"question", "answer", "text"} & set(cols)
    assert conn.execute("SELECT question_chars FROM request_log").fetchone()[0] == len("my secret question")


@pytest.fixture()
def client(db_ready):
    app.dependency_overrides[embedder_dep] = lambda: HashEmbedder()
    app.dependency_overrides[reranker_dep] = lambda: None
    with get_conn() as c:
        c.execute("DELETE FROM request_log")
    yield TestClient(app)
    app.dependency_overrides.clear()
    with get_conn() as c:
        c.execute("DELETE FROM request_log")
        c.execute("DELETE FROM documents WHERE filename LIKE 'metrictest-%'")


def test_ask_is_logged_and_shows_up_in_metrics(client):
    doc = client.post("/documents/upload", files={"file": ("metrictest-a.md", b"# Install\nRun brew install orbit.\n")}).json()
    app.dependency_overrides[provider_dep] = lambda: FakeProvider("Use brew [1].")
    assert client.post("/ask", json={"question": "brew install orbit", "document_ids": [doc["document_id"]]}).status_code == 200
    m = client.get("/metrics").json()
    assert m["requests"] == 1 and m["by_status"] == {"answered": 1}
    assert m["prompt_tokens"] == 10 and m["completion_tokens"] == 5 and m["error_rate"] == 0


def test_provider_failure_is_logged_as_error(client):
    class Boom(FakeProvider):
        def generate(self, prompt, system=None):
            raise ProviderError("down")

    doc = client.post("/documents/upload", files={"file": ("metrictest-b.md", b"# Install\nRun brew install orbit.\n")}).json()
    app.dependency_overrides[provider_dep] = lambda: Boom()
    assert client.post("/ask", json={"question": "brew install orbit", "document_ids": [doc["document_id"]]}).status_code == 502
    m = client.get("/metrics?hours=1").json()
    assert m["requests"] == 1 and m["by_status"] == {"error": 1} and m["error_rate"] == 1.0


def test_cache_hit_is_logged_with_zero_cost_and_shows_in_metrics(client):
    doc = client.post("/documents/upload", files={"file": ("metrictest-c.md", b"# Install\nRun brew install orbit.\n")}).json()
    p = FakeProvider("Use brew [1].")
    p.model = "gemini-2.0-flash"                      # a priced model, so a miss costs something
    app.dependency_overrides[provider_dep] = lambda: p
    body = {"question": "brew install orbit", "document_ids": [doc["document_id"]]}
    assert client.post("/ask", json=body).json()["cache"] == "miss"
    again = client.post("/ask", json=body).json()
    assert again["cache"] == "exact" and again["prompt_tokens"] is None and len(p.calls) == 1
    m = client.get("/metrics").json()
    assert m["requests"] == 2 and m["cache_hit_rate"] == 0.5
    assert m["prompt_tokens"] == 10                   # only the miss spent tokens
