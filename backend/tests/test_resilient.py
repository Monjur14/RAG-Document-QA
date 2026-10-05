import httpx
import pytest

from app import config
from app.hosted import GeminiProvider, OpenAIProvider, OpenRouterProvider
from app.providers import LLMResponse, OllamaProvider, ProviderError, get_provider, retryable_status
from app.resilient import ResilientProvider


class Scripted:
    """A provider that plays back a list of outcomes: an exception to raise, or text to return."""

    def __init__(self, model, *outcomes):
        self.model, self.outcomes, self.calls = model, list(outcomes), 0

    def generate(self, prompt, system=None):
        self.calls += 1
        o = self.outcomes.pop(0) if self.outcomes else "ok"
        if isinstance(o, Exception):
            raise o
        return LLMResponse(text=o, model=self.model, prompt_tokens=1, completion_tokens=1, latency_ms=1.0)


class Clock:
    def __init__(self):
        self.t, self.sleeps = 0.0, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def chain(*providers, **kw):
    c = Clock()
    return ResilientProvider(list(providers), sleep=c.sleep, clock=c.now, **kw), c


def test_retryable_status_codes():
    assert retryable_status(429) and retryable_status(503) and retryable_status(408)
    assert not retryable_status(400) and not retryable_status(401) and not retryable_status(404)


def test_retries_a_transient_error_with_exponential_backoff_then_succeeds():
    a = Scripted("a", ProviderError("conn"), ProviderError("conn"), "hello")
    r, clock = chain(a, max_retries=2, backoff_s=0.5)
    assert r.generate("q").text == "hello" and a.calls == 3 and clock.sleeps == [0.5, 1.0]


def test_falls_back_to_the_next_provider_and_reports_who_answered():
    a = Scripted("a", *[ProviderError("down")] * 3)
    b = Scripted("b", "from b")
    r, _ = chain(a, b, max_retries=2)
    resp = r.generate("q")
    assert resp.text == "from b" and resp.model == "b" and a.calls == 3 and b.calls == 1
    assert r.model == "a"                                       # the primary's name, for cache scoping


def test_non_retryable_error_skips_retries_and_goes_to_the_next_provider():
    a = Scripted("a", ProviderError("timed out", retryable=False))
    b = Scripted("b", "ok b")
    r, clock = chain(a, b, max_retries=2)
    assert r.generate("q").model == "b" and a.calls == 1 and clock.sleeps == []


def test_failed_provider_is_skipped_during_cooldown_and_retried_afterwards():
    a = Scripted("a", ProviderError("down", retryable=False), "a is back")
    b = Scripted("b", "b1", "b2", "b3")
    r, clock = chain(a, b, cooldown_s=30)
    assert r.generate("q").model == "b"                         # a fails once, b answers
    assert r.generate("q").model == "b" and a.calls == 1        # a is not even tried during the cooldown
    clock.t += 31
    assert r.generate("q").model == "a" and a.calls == 2        # cooldown over: a is tried again and recovers


def test_all_providers_failing_raises_one_error_naming_every_reason():
    r, _ = chain(Scripted("a", ProviderError("boom A", retryable=False)), Scripted("b", ProviderError("boom B", retryable=False)))
    with pytest.raises(ProviderError) as e:
        r.generate("q")
    assert "boom A" in str(e.value) and "boom B" in str(e.value)


def test_if_every_provider_is_cooling_down_they_are_all_tried_anyway():
    a = Scripted("a", ProviderError("x", retryable=False), "a recovered")
    r, _ = chain(a)
    with pytest.raises(ProviderError):
        r.generate("q")
    assert r.generate("q").text == "a recovered"                # not locked out for the whole cooldown


# ---- hosted adapters ----
def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gemini_request_shape_and_parsing():
    seen = {}

    def handler(request):
        seen["url"], seen["key"], seen["body"] = str(request.url), request.headers.get("x-goog-api-key"), request.read()
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Hi "}, {"text": "there [1]"}]}}],
                                         "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 4}})

    import json

    p = GeminiProvider("secret-key", model="g1", base_url="https://g.test/v1beta", client=client(handler))
    r = p.generate("question?", system="rules")
    body = json.loads(seen["body"])
    assert seen["url"] == "https://g.test/v1beta/models/g1:generateContent" and seen["key"] == "secret-key"
    assert "secret-key" not in seen["url"]                      # the key travels in a header, never in the URL
    assert body["systemInstruction"]["parts"][0]["text"] == "rules" and body["generationConfig"]["temperature"] == 0
    assert body["contents"][0]["parts"][0]["text"] == "question?"
    assert (r.text, r.prompt_tokens, r.completion_tokens, r.model) == ("Hi there [1]", 11, 4, "g1")


def test_gemini_errors_are_classified():
    def status(code):
        return GeminiProvider("k", client=client(lambda req: httpx.Response(code, text="x")))

    with pytest.raises(ProviderError) as e:
        status(429).generate("q")
    assert e.value.retryable
    with pytest.raises(ProviderError) as e:
        status(401).generate("q")
    assert not e.value.retryable
    blocked = GeminiProvider("k", client=client(lambda req: httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY"}]})))
    with pytest.raises(ProviderError) as e:
        blocked.generate("q")
    assert "SAFETY" in str(e.value) and not e.value.retryable


def test_timeout_is_not_retried_but_connection_errors_are():
    def timeout(req):
        raise httpx.ReadTimeout("slow")

    def refused(req):
        raise httpx.ConnectError("nope")

    with pytest.raises(ProviderError) as e:
        OpenRouterProvider("k", client=client(timeout)).generate("q")
    assert not e.value.retryable
    with pytest.raises(ProviderError) as e:
        OpenRouterProvider("k", client=client(refused)).generate("q")
    assert e.value.retryable


def test_openrouter_request_shape_parsing_and_200_with_error_object():
    import json

    seen = {}

    def ok(request):
        seen["auth"], seen["body"] = request.headers["authorization"], json.loads(request.read())
        return httpx.Response(200, json={"choices": [{"message": {"content": " Yes [1] "}}], "usage": {"prompt_tokens": 7, "completion_tokens": 2}})

    r = OpenRouterProvider("k1", model="m", base_url="https://or.test/api/v1", client=client(ok)).generate("q", system="s")
    assert seen["auth"] == "Bearer k1" and seen["body"]["messages"][0] == {"role": "system", "content": "s"}
    assert (r.text, r.prompt_tokens, r.completion_tokens) == ("Yes [1]", 7, 2)

    err = OpenRouterProvider("k", client=client(lambda req: httpx.Response(200, json={"error": {"message": "rate limited", "code": 429}})))
    with pytest.raises(ProviderError) as e:
        err.generate("q")
    assert e.value.retryable and "rate limited" in str(e.value)


def test_hosted_providers_require_a_key():
    for cls in (GeminiProvider, OpenAIProvider, OpenRouterProvider):
        with pytest.raises(ValueError):
            cls("")


# ---- building the chain from configuration ----
@pytest.fixture()
def fresh(monkeypatch):
    get_provider.cache_clear()
    yield monkeypatch
    get_provider.cache_clear()


def _keys(monkeypatch, openai="", gemini="", openrouter=""):
    monkeypatch.setattr(config, "OPENAI_API_KEY", openai)
    monkeypatch.setattr(config, "GEMINI_API_KEY", gemini)
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", openrouter)


def names(p):
    return [type(x).__name__ for x in p.providers]


def test_no_keys_means_local_ollama_only(fresh):
    fresh.setattr(config, "LLM_PROVIDERS", "auto")
    _keys(fresh)
    p = get_provider()
    assert isinstance(p, ResilientProvider) and names(p) == ["OllamaProvider"]


def test_auto_prefers_openai_then_gemini_then_openrouter_and_always_ends_with_ollama(fresh):
    fresh.setattr(config, "LLM_PROVIDERS", "auto")
    _keys(fresh, openai="ok", gemini="gk", openrouter="rk")
    assert names(get_provider()) == ["OpenAIProvider", "GeminiProvider", "OpenRouterProvider", "OllamaProvider"]
    get_provider.cache_clear()
    _keys(fresh, gemini="gk")                                   # only a Gemini key: Gemini first, local as the safety net
    assert names(get_provider()) == ["GeminiProvider", "OllamaProvider"]
    get_provider.cache_clear()
    _keys(fresh, openai="ok")
    assert names(get_provider()) == ["OpenAIProvider", "OllamaProvider"]


def test_explicit_chain_follows_the_listed_order_and_skips_providers_without_keys(fresh):
    fresh.setattr(config, "LLM_PROVIDERS", "gemini, openrouter ,ollama")
    _keys(fresh, gemini="gk")                                   # no OpenRouter key: skipped, not a crash
    assert names(get_provider()) == ["GeminiProvider", "OllamaProvider"]


def test_bad_configuration_fails_loudly(fresh):
    fresh.setattr(config, "LLM_PROVIDERS", "gpt-magic")
    with pytest.raises(ValueError):
        get_provider()
    get_provider.cache_clear()
    fresh.setattr(config, "LLM_PROVIDERS", "gemini")
    _keys(fresh)
    with pytest.raises(RuntimeError):
        get_provider()


def test_openai_adapter_uses_the_openai_endpoint_and_names_itself_in_errors():
    import json

    seen = {}

    def ok(request):
        seen["url"], seen["auth"], seen["model"] = str(request.url), request.headers["authorization"], json.loads(request.read())["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "Hi [1]"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}})

    p = OpenAIProvider("sk-test", client=client(ok))
    r = p.generate("q")
    assert seen["url"] == "https://api.openai.com/v1/chat/completions" and seen["auth"] == "Bearer sk-test"
    assert r.text == "Hi [1]" and r.model == seen["model"] == config.OPENAI_MODEL
    with pytest.raises(ProviderError) as e:
        OpenAIProvider("sk", client=client(lambda req: httpx.Response(401, text="bad key"))).generate("q")
    assert "OpenAI" in str(e.value) and not e.value.retryable
