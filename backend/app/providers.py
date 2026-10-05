"""LLM provider interface. Adapters implement `generate(prompt, system) -> LLMResponse`.
Ollama (local) is first; Gemini and OpenRouter adapters, retries and fallback arrive in Week 3."""
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import LLM_TIMEOUT_S, OLLAMA_MODEL, OLLAMA_NUM_CTX, OLLAMA_THINK, OLLAMA_URL


class ProviderError(RuntimeError):
    """The LLM could not produce a response (unreachable, timed out, or returned an error).

    `retryable` says whether trying the same provider again can help (a dropped connection or HTTP 429/5xx can;
    a timeout, a bad key or blocked content cannot, so the next provider is tried instead)."""

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def retryable_status(status: int) -> bool:
    return status in (408, 425, 429) or status >= 500


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float


class LLMProvider(Protocol):
    model: str

    def generate(self, prompt: str, system: str | None = None) -> LLMResponse: ...


class OllamaProvider:
    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        base_url: str = OLLAMA_URL,
        timeout: float = LLM_TIMEOUT_S,
        num_ctx: int = OLLAMA_NUM_CTX,
        think: bool | None = OLLAMA_THINK,
        client: httpx.Client | None = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.think = think
        self._client = client or httpx.Client(timeout=timeout)

    def generate(self, prompt: str, system: str | None = None) -> LLMResponse:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        body: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",  # keep the model in GPU memory between questions
            "options": {"temperature": 0, "num_ctx": self.num_ctx},  # deterministic, enough room for the sources
        }
        if self.think is not None:
            body["think"] = self.think

        t0 = time.perf_counter()
        try:
            r = self._client.post(f"{self.base_url}/api/chat", json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Ollama timed out after {self.timeout:.0f}s", retryable=False) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc
        if r.status_code != 200:
            raise ProviderError(f"Ollama returned HTTP {r.status_code}: {r.text[:200]}", retryable=retryable_status(r.status_code))

        data = r.json()
        content = (data.get("message") or {}).get("content")
        if content is None:
            raise ProviderError("Ollama response had no message content", retryable=False)
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()  # some models inline their reasoning
        return LLMResponse(
            text=content,
            model=self.model,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


AUTO_ORDER = ["openai", "gemini", "openrouter", "ollama"]


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    """Build the provider chain, with retries and fallback (see config.LLM_PROVIDERS).

    "auto" (the default) keeps every provider that has an API key, in the order OpenAI, Gemini, OpenRouter,
    and always ends with local Ollama, so with no keys at all the app runs fully local.
    """
    import logging

    from app import config
    from app.hosted import GeminiProvider, OpenAIProvider, OpenRouterProvider
    from app.resilient import ResilientProvider

    log = logging.getLogger(__name__)
    keys = {"openai": config.OPENAI_API_KEY, "gemini": config.GEMINI_API_KEY, "openrouter": config.OPENROUTER_API_KEY}
    makers = {"openai": OpenAIProvider, "gemini": GeminiProvider, "openrouter": OpenRouterProvider}
    raw = [n.strip().lower() for n in config.LLM_PROVIDERS.split(",") if n.strip()]
    auto = raw in ([], ["auto"])
    names = AUTO_ORDER if auto else raw

    providers: list[LLMProvider] = []
    for name in names:
        if name == "ollama":
            providers.append(OllamaProvider())
        elif name in makers:
            if keys[name]:
                providers.append(makers[name](keys[name]))
            elif not auto:
                log.warning("LLM_PROVIDERS lists %s but its API key is not set; skipping it", name)
        else:
            raise ValueError(f"Unknown provider {name!r} in LLM_PROVIDERS (use auto, openai, gemini, openrouter, ollama)")
    if not providers:
        raise RuntimeError("No usable LLM provider: check LLM_PROVIDERS and the API key variables")
    log.info("LLM chain: %s", " -> ".join(getattr(p, "model", type(p).__name__) for p in providers))
    return ResilientProvider(providers, max_retries=config.LLM_MAX_RETRIES, backoff_s=config.LLM_BACKOFF_S,
                             cooldown_s=config.LLM_COOLDOWN_S)
