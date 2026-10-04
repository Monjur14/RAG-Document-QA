"""Cross-encoder reranking: re-score the retriever's candidate pool by reading query and passage
together. Slower than vector search (one model pass per candidate) but much better at picking the
best passage among several near neighbours.

The heavy imports are lazy, like app/embeddings.py.
"""
import os
from dataclasses import replace
from typing import Protocol

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from app.config import RERANK_MODEL


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


def passage_text(hit) -> str:
    return f"{hit.heading}\n\n{hit.text}" if hit.heading else hit.text


def rerank(query: str, hits: list, reranker: Reranker, k: int) -> list:
    """Return the top-k hits ordered by reranker score. Original retrieval fields (vector_score, ranks)
    are preserved so the refusal threshold still works; `score` becomes the reranker score."""
    if not hits:
        return []
    scores = reranker.score(query, [passage_text(h) for h in hits])
    ordered = sorted(zip(hits, scores), key=lambda p: (-p[1], p[0].chunk_id))
    return [replace(h, score=float(s), rerank_score=float(s)) for h, s in ordered[:k]]


class CrossEncoderReranker:
    def __init__(self, model_name: str = RERANK_MODEL, device: str | None = None, batch_size: int = 16):
        self.model_name = model_name
        self.batch_size = batch_size
        self._requested_device = device
        self._model = None
        self.device: str | None = None

    def _load(self):
        if self._model is None:
            import torch
            from sentence_transformers import CrossEncoder

            self.device = self._requested_device or ("cuda" if torch.cuda.is_available() else "cpu")
            self._model = CrossEncoder(self.model_name, device=self.device)
        return self._model

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        preds = self._load().predict(
            [(query, p) for p in passages], batch_size=self.batch_size, show_progress_bar=False
        )
        return [float(x) for x in preds]


_default: CrossEncoderReranker | None = None


def get_reranker() -> CrossEncoderReranker:
    global _default
    if _default is None:
        _default = CrossEncoderReranker()
    return _default
