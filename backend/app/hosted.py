"""Hosted LLM adapters (OpenAI, Gemini, OpenRouter) behind the same `generate(prompt, system) -> LLMResponse` interface.

API keys come from environment variables (see app/config.py), travel only in request headers, and are never logged.
Hosted prices change: check each provider's current free-tier terms before relying on them.
"""
import time

import httpx

from app.config import GEMINI_MODEL, LLM_TIMEOUT_S, OPENAI_MODEL, OPENROUTER_MODEL
from app.providers import LLMResponse, ProviderError, retryable_status


def _post_json(client: httpx.Client, name: str, url: str, headers: dict, body: dict, timeout: float) -> dict:
    try:
        r = client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        # Retrying a slow provider only makes the user wait longer: fall over to the next provider instead.
        raise ProviderError(f"{name} timed out after {timeout:.0f}s", retryable=False) from exc
    except httpx.HTTPError as exc:
        raise ProviderError(f"Cannot reach {name}: {type(exc).__name__}") from exc
    if r.status_code != 200:
        raise ProviderError(f"{name} returned HTTP {r.status_code}: {r.text[:200]}", retryable=retryable_status(r.status_code))
    try:
        return r.json()
    except ValueError as exc:
        raise ProviderError(f"{name} returned invalid JSON") from exc


class GeminiProvider:
    def __init__(self, api_key: str, model: str = GEMINI_MODEL, base_url: str = "https://generativelanguage.googleapis.com/v1beta",
                 timeout: float = LLM_TIMEOUT_S, client: httpx.Client | None = None):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self.model, self.base_url, self.timeout = model, base_url.rstrip("/"), timeout
        self._key = api_key
        self._client = client or httpx.Client(timeout=timeout)

    def generate(self, prompt: str, system: str | None = None) -> LLMResponse:
        body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        t0 = time.perf_counter()
        data = _post_json(self._client, "Gemini", f"{self.base_url}/models/{self.model}:generateContent",
                          {"x-goog-api-key": self._key}, body, self.timeout)
        candidates = data.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            reason = (candidates[0].get("finishReason") if candidates else None) or (data.get("promptFeedback") or {}).get("blockReason")
            raise ProviderError(f"Gemini returned no text (reason: {reason or 'unknown'})", retryable=False)
        usage = data.get("usageMetadata") or {}
        return LLMResponse(text=text, model=self.model, prompt_tokens=usage.get("promptTokenCount"),
                           completion_tokens=usage.get("candidatesTokenCount"), latency_ms=(time.perf_counter() - t0) * 1000)


class OpenAICompatibleProvider:
    """Any service that speaks the OpenAI chat-completions format (OpenAI itself, OpenRouter, ...)."""

    name = "OpenAI-compatible"

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = LLM_TIMEOUT_S,
                 client: httpx.Client | None = None):
        if not api_key:
            raise ValueError(f"{self.name} API key is not set")
        self.model, self.base_url, self.timeout = model, base_url.rstrip("/"), timeout
        self._key = api_key
        self._client = client or httpx.Client(timeout=timeout)

    def generate(self, prompt: str, system: str | None = None) -> LLMResponse:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        t0 = time.perf_counter()
        data = _post_json(self._client, self.name, f"{self.base_url}/chat/completions",
                          {"Authorization": f"Bearer {self._key}"},
                          {"model": self.model, "messages": messages, "temperature": 0}, self.timeout)
        if data.get("error"):  # some services answer HTTP 200 with an error object
            err = data["error"] if isinstance(data["error"], dict) else {"message": str(data["error"])}
            code = str(err.get("code", ""))
            raise ProviderError(f"{self.name} error: {str(err.get('message', 'unknown'))[:200]}",
                                retryable=retryable_status(int(code)) if code.isdigit() else True)
        choices = data.get("choices") or []
        text = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
        if not text:
            raise ProviderError(f"{self.name} returned no text", retryable=False)
        usage = data.get("usage") or {}
        return LLMResponse(text=text, model=self.model, prompt_tokens=usage.get("prompt_tokens"),
                           completion_tokens=usage.get("completion_tokens"), latency_ms=(time.perf_counter() - t0) * 1000)


class OpenAIProvider(OpenAICompatibleProvider):
    name = "OpenAI"

    def __init__(self, api_key: str, model: str = OPENAI_MODEL, base_url: str = "https://api.openai.com/v1",
                 timeout: float = LLM_TIMEOUT_S, client: httpx.Client | None = None):
        super().__init__(api_key, model, base_url, timeout, client)


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "OpenRouter"

    def __init__(self, api_key: str, model: str = OPENROUTER_MODEL, base_url: str = "https://openrouter.ai/api/v1",
                 timeout: float = LLM_TIMEOUT_S, client: httpx.Client | None = None):
        super().__init__(api_key, model, base_url, timeout, client)
