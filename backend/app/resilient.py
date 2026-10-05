"""Retries with backoff, per-provider cooldown, and ordered fallback across providers.

For each provider in order: try up to 1 + max_retries times, waiting backoff * 2**attempt between tries, but only for
errors marked retryable (connection failures, HTTP 429/5xx). Non-retryable errors (timeouts, bad key, blocked content)
move on to the next provider at once. A provider that fails is skipped for `cooldown_s` seconds so a dead provider
does not add its retry delays to every request. If every provider fails, one ProviderError lists all the reasons.
"""
import time

from app.providers import LLMProvider, LLMResponse, ProviderError


class ResilientProvider:
    def __init__(self, providers: list[LLMProvider], *, max_retries: int = 2, backoff_s: float = 0.5,
                 cooldown_s: float = 30.0, sleep=time.sleep, clock=time.monotonic):
        if not providers:
            raise ValueError("at least one provider is required")
        self.providers = providers
        self.model = getattr(providers[0], "model", type(providers[0]).__name__)  # primary; each response names the model that really answered
        self.max_retries, self.backoff_s, self.cooldown_s = max_retries, backoff_s, cooldown_s
        self._sleep, self._clock = sleep, clock
        self._down_until: dict[int, float] = {}

    def generate(self, prompt: str, system: str | None = None) -> LLMResponse:
        now = self._clock()
        order = [p for p in self.providers if self._down_until.get(id(p), 0.0) <= now] or list(self.providers)
        errors: list[str] = []
        for provider in order:
            name = getattr(provider, "model", type(provider).__name__)
            for attempt in range(self.max_retries + 1):
                try:
                    resp = provider.generate(prompt, system=system)
                except ProviderError as exc:
                    errors.append(f"{name}: {exc}")
                    if not exc.retryable:
                        break
                    if attempt < self.max_retries:
                        self._sleep(self.backoff_s * 2 ** attempt)
                    continue
                self._down_until.pop(id(provider), None)
                return resp
            self._down_until[id(provider)] = self._clock() + self.cooldown_s
        raise ProviderError("All LLM providers failed: " + "; ".join(errors), retryable=False)
