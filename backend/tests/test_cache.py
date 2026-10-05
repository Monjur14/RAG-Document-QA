import uuid

import pytest

from app import cache
from app.db import get_conn
from app.ingest import ingest_document
from tests.fakes import FakeProvider, HashEmbedder

Q = "How do I install Orbit with brew?"


@pytest.fixture()
def doc(db_ready):
    prefix = f"cachetest-{uuid.uuid4().hex[:8]}"
    r = ingest_document(get_conn, HashEmbedder(), f"{prefix}.md",
                        b"# Install\nInstall Orbit with brew install orbit on macOS.\n\n# Uninstall\nRemove the package.\n")
    with get_conn() as c:
        c.execute("DELETE FROM answer_cache")
    yield r.document_id
    with get_conn() as c:
        c.execute("DELETE FROM answer_cache")
        c.execute("DELETE FROM documents WHERE filename LIKE %s", (f"{prefix}%",))


def ask(provider, question, doc_id, **kw):
    with get_conn() as c:
        return cache.answer_with_cache(c, HashEmbedder(), provider, question, document_ids=[doc_id], min_score=0.2, **kw)


def test_normalize_ignores_case_spacing_and_trailing_punctuation():
    assert cache.normalize("  How do I   install Orbit?? ") == cache.normalize("how do i install orbit")


def test_second_identical_question_is_an_exact_hit_and_skips_the_llm(doc):
    p = FakeProvider("Use brew install orbit [1].")
    first = ask(p, Q, doc)
    second = ask(p, "  how do i INSTALL orbit with brew  ", doc)
    assert first.cache == "miss" and second.cache == "exact"
    assert len(p.calls) == 1                                   # the LLM ran once
    assert second.answer == first.answer and second.citations[0].heading == "Install"
    assert second.prompt_tokens is None and second.completion_tokens is None
    assert second.question == "  how do i INSTALL orbit with brew  "


def test_reworded_question_is_a_semantic_hit_only_above_the_threshold(doc):
    p = FakeProvider("Use brew install orbit [1].")
    ask(p, "install orbit brew macOS how", doc)
    reordered = ask(p, "how macOS brew orbit install", doc)   # same words: identical embedding, different text
    assert reordered.cache == "semantic" and len(p.calls) == 1
    different = ask(p, "remove the package", doc)             # a genuinely different question must not hit
    assert different.cache == "miss" and len(p.calls) == 2
    strict = ask(p, "macOS orbit brew install how extra words appear here", doc, threshold=0.999)
    assert strict.cache == "miss"


def test_uploading_a_document_invalidates_the_cache(doc):
    p = FakeProvider("Use brew install orbit [1].")
    ask(p, Q, doc)
    assert ask(p, Q, doc).cache == "exact"
    other = ingest_document(get_conn, HashEmbedder(), f"cachetest-{uuid.uuid4().hex[:8]}-other.md", b"# Other\nUnrelated text.\n")
    try:
        assert ask(p, Q, doc).cache == "miss"                   # the document set changed
    finally:
        with get_conn() as c:
            c.execute("DELETE FROM documents WHERE id = %s", (other.document_id,))
    assert ask(p, Q, doc).cache == "miss"                      # deleting changes it again


def test_settings_and_model_changes_do_not_share_answers(doc):
    p = FakeProvider("Use brew install orbit [1].")
    ask(p, Q, doc)
    other_model = FakeProvider("Use brew install orbit [1].")
    other_model.model = "another-model"
    assert ask(other_model, Q, doc).cache == "miss"
    assert ask(p, Q, doc, k=3).cache == "miss"
    assert ask(p, Q, doc, mode="vector").cache == "miss"


def test_only_answered_results_are_cached(doc):
    declined, uncited = FakeProvider("I don't know."), FakeProvider("Probably just run it.")
    assert ask(declined, Q, doc).status == "model_declined" and ask(declined, Q, doc).cache == "miss"
    assert ask(uncited, Q, doc).status == "uncited" and ask(uncited, Q, doc).cache == "miss"
    with get_conn() as c:
        assert c.execute("SELECT count(*) FROM answer_cache").fetchone()[0] == 0


def test_cache_can_be_turned_off(doc):
    p = FakeProvider("Use brew install orbit [1].")
    ask(p, Q, doc, enabled=False)
    assert ask(p, Q, doc, enabled=False).cache == "miss" and len(p.calls) == 2
    with get_conn() as c:
        assert c.execute("SELECT count(*) FROM answer_cache").fetchone()[0] == 0
