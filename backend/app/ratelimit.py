"""Per-client rate limiting for the expensive endpoints (/ask calls an LLM, /documents/upload parses and embeds).

Sliding window kept in memory, keyed by the client IP the connection came from. Single-instance app, so memory is
enough; with several workers each would count separately. X-Forwarded-For is deliberately NOT trusted: a client can
set it to any value and dodge the limit. Behind a reverse proxy, configure the proxy to rate-limit instead.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app import config


class RateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0, clock=time.monotonic):
        self.limit, self.window_s, self.clock = limit, window_s, clock
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> float | None:
        """Record a request. Returns None if allowed, else the seconds until the client may retry."""
        if self.limit <= 0:
            return None
        now = self.clock()
        q = self._hits[key]
        while q and now - q[0] >= self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return self.window_s - (now - q[0])
        q.append(now)
        if len(self._hits) > 10_000:   # forget clients that have gone quiet
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window_s]:
                del self._hits[k]
        return None


_limiters: dict[str, RateLimiter] = {}


def reset() -> None:
    _limiters.clear()


def _limit_for(name: str) -> int:
    return config.RATE_LIMIT_ASK_PER_MIN if name == "ask" else config.RATE_LIMIT_UPLOAD_PER_MIN


def rate_limit(name: str):
    """FastAPI dependency: `dependencies=[Depends(rate_limit("ask"))]`. 429 with a Retry-After header when exceeded."""
    def dep(request: Request) -> None:
        if not config.RATE_LIMIT_ENABLED:
            return
        limiter = _limiters.setdefault(name, RateLimiter(_limit_for(name)))
        wait = limiter.check(request.client.host if request.client else "unknown")
        if wait is not None:
            raise HTTPException(429, f"Too many requests. Try again in {int(wait) + 1} s.",
                                headers={"Retry-After": str(int(wait) + 1)})
    return dep
