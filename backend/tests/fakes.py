"""Deterministic stand-in for the real embedding model so tests are fast and need no GPU/download.
Hashes words into a 384-d vector, so texts that share words end up close together."""
import math
import re
import zlib

from app.config import EMBEDDING_DIM


class HashEmbedder:
    def _vec(self, text: str) -> list[float]:
        v = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            v[zlib.crc32(word.encode()) % EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FailingEmbedder:
    def embed_documents(self, texts):
        raise RuntimeError("boom")

    def embed_query(self, text):
        raise RuntimeError("boom")


class FakeProvider:
    """Stands in for an LLM: returns a canned reply and records what it was asked."""

    model = "fake"

    def __init__(self, reply: str = "Answer [1]."):
        self.reply = reply
        self.calls: list[tuple[str | None, str]] = []

    def generate(self, prompt, system=None):
        from app.providers import LLMResponse

        self.calls.append((system, prompt))
        return LLMResponse(text=self.reply, model="fake", prompt_tokens=10, completion_tokens=5, latency_ms=1.0)


class WordOverlapReranker:
    """Deterministic stand-in for a cross-encoder: score = number of query words found in the passage."""

    model_name = "word-overlap"

    def score(self, query: str, passages: list[str]) -> list[float]:
        q = set(query.lower().split())
        return [float(len(q & set(p.lower().split()))) for p in passages]
