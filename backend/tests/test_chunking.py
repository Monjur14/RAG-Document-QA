import pytest

from app.chunking import ChunkConfig, chunk_sections
from app.models import ParsedSection


def sec(text, heading=None, page=None, source="d.md"):
    return ParsedSection(text=text, heading=heading, page=page, source=source)


def test_config_validation():
    with pytest.raises(ValueError):
        ChunkConfig(chunk_size=0)
    with pytest.raises(ValueError):
        ChunkConfig(chunk_size=100, overlap=100)


def test_empty_input():
    assert chunk_sections([]) == []
    assert chunk_sections([], ChunkConfig(strategy="fixed")) == []


def test_heading_strategy_never_crosses_headings():
    s = [sec("alpha text", "A"), sec("beta text", "B")]
    out = chunk_sections(s, ChunkConfig(strategy="heading", chunk_size=1000))
    assert [(c.heading, c.text) for c in out] == [("A", "alpha text"), ("B", "beta text")]


def test_heading_strategy_packs_small_paragraphs():
    s = [sec("one", "A"), sec("two", "A"), sec("three", "A")]
    out = chunk_sections(s, ChunkConfig(chunk_size=1000))
    assert len(out) == 1 and out[0].text == "one\n\ntwo\n\nthree"


def test_heading_strategy_respects_size_when_packing():
    s = [sec("x" * 60, "A"), sec("y" * 60, "A")]
    out = chunk_sections(s, ChunkConfig(chunk_size=100, overlap=10))
    assert len(out) == 2 and all(len(c.text) <= 100 for c in out)


def test_heading_strategy_splits_oversized_block_with_overlap():
    words = " ".join(f"w{i}" for i in range(200))
    out = chunk_sections([sec(words, "A")], ChunkConfig(chunk_size=100, overlap=20))
    assert len(out) > 1
    assert all(len(c.text) <= 100 and c.heading == "A" for c in out)
    # neighbouring chunks share some text
    assert set(out[0].text.split()) & set(out[1].text.split())


def test_page_boundaries_are_kept():
    s = [sec("p1 text", "H", page=1), sec("p2 text", "H", page=2)]
    out = chunk_sections(s, ChunkConfig(chunk_size=1000))
    assert [c.page for c in out] == [1, 2]


def test_fixed_strategy_ignores_headings_but_keeps_start_metadata():
    s = [sec("a" * 50, "A"), sec("b" * 50, "B")]
    out = chunk_sections(s, ChunkConfig(strategy="fixed", chunk_size=80, overlap=10))
    assert len(out) >= 2
    assert out[0].heading == "A"
    assert all(len(c.text) <= 80 for c in out)


def test_fixed_covers_all_words_and_makes_progress():
    words = [f"w{i}" for i in range(300)]
    out = chunk_sections([sec(" ".join(words), "A")], ChunkConfig(strategy="fixed", chunk_size=120, overlap=30))
    seen = {w for c in out for w in c.text.split()}
    assert seen == set(words)


def test_chunk_indexes_are_sequential():
    s = [sec("x" * 90, "A"), sec("y" * 90, "B"), sec("z" * 90, "C")]
    out = chunk_sections(s, ChunkConfig(chunk_size=100, overlap=10))
    assert [c.chunk_index for c in out] == list(range(len(out)))
