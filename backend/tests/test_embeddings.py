import math
import os

import pytest

from app.chunking import Chunk
from app.config import EMBEDDING_DIM
from app.embeddings import chunk_embedding_text, get_embedder
from tests.fakes import HashEmbedder


def test_chunk_embedding_text_includes_heading():
    c = Chunk(text="body", chunk_index=0, source="a.md", heading="Setup")
    assert chunk_embedding_text(c) == "Setup\n\nbody"
    assert chunk_embedding_text(Chunk(text="body", chunk_index=0, source="a.md")) == "body"


def test_fake_embedder_shape_and_similarity():
    e = HashEmbedder()
    a, b, c = e.embed_documents(["postgres vector search", "vector search in postgres", "yellow bananas"])
    assert len(a) == EMBEDDING_DIM
    assert math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-6)
    dot = lambda u, v: sum(x * y for x, y in zip(u, v))
    assert dot(a, b) > dot(a, c)


def test_get_embedder_is_cached_and_lazy():
    assert get_embedder() is get_embedder()  # does not load the model


@pytest.mark.skipif(os.getenv("RUN_MODEL_TESTS") != "1", reason="set RUN_MODEL_TESTS=1 to run with the real model")
def test_real_model_ranks_relevant_passage_first():
    e = get_embedder()
    docs = ["PostgreSQL with pgvector supports vector similarity search.", "Bananas are yellow.", "FastAPI is a web framework."]
    vecs = e.embed_documents(docs)
    q = e.embed_query("Which database can do vector search?")
    scores = [sum(a * b for a, b in zip(q, v)) for v in vecs]
    assert len(q) == EMBEDDING_DIM
    assert scores.index(max(scores)) == 0
    assert math.isclose(sum(x * x for x in q), 1.0, rel_tol=1e-3)
