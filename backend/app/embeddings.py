"""Local text embeddings (sentence-transformers on PyTorch, GPU when available).

Run `python -m app.embeddings` for a quick smoke test of the real model.
The heavy imports are lazy, so importing this module (and running most tests) is cheap.
"""
import os
from functools import lru_cache
from typing import Protocol

# Windows without Developer Mode cannot use symlinks; the cache still works, so hide the warning.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from app.chunking import Chunk
from app.config import EMBEDDING_DIM, EMBEDDING_MODEL

# bge models are trained so that *queries* carry this instruction and *passages* do not.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def chunk_embedding_text(chunk: Chunk) -> str:
    """Text that gets embedded for a chunk: the heading gives the passage its context."""
    return f"{chunk.heading}\n\n{chunk.text}" if chunk.heading else chunk.text


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL, device: str | None = None, batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size
        self._requested_device = device
        self._model = None
        self.device: str | None = None

    def _load(self):
        if self._model is None:
            import torch
            from sentence_transformers import SentenceTransformer

            self.device = self._requested_device or ("cuda" if torch.cuda.is_available() else "cpu")
            model = SentenceTransformer(self.model_name, device=self.device)
            get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
            dim = get_dim()
            if dim != EMBEDDING_DIM:
                raise RuntimeError(
                    f"Model {self.model_name} produces {dim}-d vectors but the database column is "
                    f"vector({EMBEDDING_DIM}). Add a migration and re-index to change models."
                )
            self._model = model
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vecs = self._load().encode(
            texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return vecs.tolist()

    def embed_query(self, text: str) -> list[float]:
        vec = self._load().encode(QUERY_PREFIX + text, normalize_embeddings=True, show_progress_bar=False)
        return vec.tolist()


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """One shared embedder per process; the model itself loads on first use."""
    return SentenceTransformerEmbedder()


if __name__ == "__main__":
    import time

    emb = SentenceTransformerEmbedder()
    docs = [
        "PostgreSQL with the pgvector extension stores vectors and supports similarity search.",
        "Bananas are a yellow fruit that grows in tropical climates.",
        "FastAPI is a Python web framework for building APIs.",
    ]
    t0 = time.perf_counter()
    doc_vecs = emb.embed_documents(docs)  # includes one-time model load
    t1 = time.perf_counter()
    question = "Which database can do vector search?"
    q = emb.embed_query(question)
    print(f"model={emb.model_name} device={emb.device} dim={len(q)} first_call={t1 - t0:.1f}s")
    print(f"question: {question}")
    scores = sorted(((sum(a * b for a, b in zip(q, v)), d) for v, d in zip(doc_vecs, docs)), reverse=True)
    for score, d in scores:
        print(f"  {score:.3f}  {d}")
