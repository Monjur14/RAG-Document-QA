import os
import sys

import pytest
from fastapi.testclient import TestClient

from app import config, ratelimit
from app.main import app, embedder_dep, provider_dep, reranker_dep
from app.parsers import MalformedFile, UnsupportedFormat
from app.ratelimit import RateLimiter
from app.sandbox import _child_env, parse_sandboxed, parse_upload
from tests import make_docs
from tests.fakes import FakeProvider, HashEmbedder


# ---- rate limiter ----
def test_rate_limiter_blocks_after_the_limit_and_recovers():
    t = [0.0]
    rl = RateLimiter(3, 60, clock=lambda: t[0])
    assert [rl.check("a") for _ in range(3)] == [None, None, None]
    wait = rl.check("a")
    assert wait is not None and 0 < wait <= 60
    assert rl.check("b") is None                 # another client is unaffected
    t[0] = 61
    assert rl.check("a") is None                 # window passed


def test_rate_limiter_zero_means_unlimited():
    rl = RateLimiter(0)
    assert all(rl.check("a") is None for _ in range(100))


def test_ask_endpoint_returns_429_with_retry_after(db_ready, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_ASK_PER_MIN", 2)
    ratelimit.reset()
    app.dependency_overrides[embedder_dep] = lambda: HashEmbedder()
    app.dependency_overrides[reranker_dep] = lambda: None
    app.dependency_overrides[provider_dep] = lambda: FakeProvider("x [1]")
    try:
        c = TestClient(app)
        codes = [c.post("/ask", json={"question": "what is orbit"}).status_code for _ in range(3)]
        assert codes[2] == 429 and 429 not in codes[:2]
        r = c.post("/ask", json={"question": "what is orbit"})
        assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
        assert c.get("/health").status_code == 200          # cheap endpoints are not limited
    finally:
        app.dependency_overrides.clear()


def test_upload_endpoint_is_limited_too(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_UPLOAD_PER_MIN", 1)
    ratelimit.reset()
    c = TestClient(app)
    first = c.post("/documents/upload", files={"file": ("x.exe", b"abc")})   # rejected (415) but still counted
    second = c.post("/documents/upload", files={"file": ("x.exe", b"abc")})
    assert first.status_code == 415 and second.status_code == 429


# ---- sandboxed parsing ----
def test_sandbox_gives_the_same_result_as_in_process_parsing():
    from app.parsers import parse_file

    for name, raw in [("a.md", b"# Title\nSome text here.\n"), ("g.pdf", make_docs.make_pdf()), ("h.docx", make_docs.make_docx())]:
        assert parse_sandboxed(name, raw) == parse_file(name, raw)


def test_sandbox_reports_bad_files_with_the_same_errors():
    with pytest.raises(UnsupportedFormat):
        parse_sandboxed("x.exe", b"abc")
    with pytest.raises(MalformedFile):
        parse_sandboxed("x.pdf", b"%PDF-1.4\nthis is garbage")
    with pytest.raises(MalformedFile):
        parse_sandboxed("x.docx", make_docs.make_zip_bomb_docx())


def test_sandbox_stops_a_parser_that_hangs(monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_TIMEOUT_S", 1.0)
    monkeypatch.setattr("app.sandbox.sys.executable", sys.executable)
    # Make the child run something that never finishes instead of the real worker.
    import subprocess

    real_run = subprocess.run

    def hanging_run(cmd, **kw):
        return real_run([sys.executable, "-c", "import time; time.sleep(30)"], **kw)

    monkeypatch.setattr("app.sandbox.subprocess.run", hanging_run)
    with pytest.raises(MalformedFile, match="longer than"):
        parse_sandboxed("a.txt", b"hello")


def test_sandbox_reports_a_crashing_parser(monkeypatch):
    import subprocess

    real_run = subprocess.run
    monkeypatch.setattr("app.sandbox.subprocess.run",
                        lambda cmd, **kw: real_run([sys.executable, "-c", "import os; os._exit(139)"], **kw))
    with pytest.raises(MalformedFile, match="could not be parsed safely"):
        parse_sandboxed("a.txt", b"hello")


def test_child_environment_has_no_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    env = _child_env()
    assert "OPENAI_API_KEY" not in env and "DATABASE_URL" not in env and env["RAG_SANDBOX_WORKER"] == "1"


def test_worker_does_not_load_the_env_file():
    import subprocess

    code = "import os; os.environ['RAG_SANDBOX_WORKER']='1'; from app import config; print(config.OPENAI_API_KEY)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={**os.environ, "OPENAI_API_KEY": ""}, cwd=os.path.dirname(os.path.dirname(__file__)))
    assert out.stdout.strip() in ("", "None")


def test_sandbox_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(config, "SANDBOX_PARSING", False)
    monkeypatch.setattr("app.sandbox.parse_sandboxed", lambda *a: (_ for _ in ()).throw(AssertionError("used the sandbox")))
    assert parse_upload("a.txt", b"hello there")[0].text == "hello there"
