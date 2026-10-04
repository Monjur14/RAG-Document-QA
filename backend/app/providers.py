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
    """The LLM could not produce a response (unreachable, timed out, or returned an error)."""


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
            raise ProviderError(f"Ollama timed out after {self.timeout:.0f}s") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc
        if r.status_code != 200:
            raise ProviderError(f"Ollama returned HTTP {r.status_code}: {r.text[:200]}")

        data = r.json()
        content = (data.get("message") or {}).get("content")
        if content is None:
            raise ProviderError("Ollama response had no message content")
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()  # some models inline their reasoning
        return LLMResponse(
            text=content,
            model=self.model,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    return OllamaProvider()
