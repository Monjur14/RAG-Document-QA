import pytest

from app.parsers import MalformedFile, UnsupportedFormat, parse_file


def test_txt_splits_paragraphs():
    out = parse_file("a.txt", b"First para.\n\nSecond para.\n\n\n")
    assert [s.text for s in out] == ["First para.", "Second para."]
    assert all(s.source == "a.txt" and s.page is None for s in out)


def test_markdown_tracks_headings():
    md = b"# Title\nintro\n\n## Setup\nstep one\n\n## Usage\nrun it\n"
    out = parse_file("r.md", md)
    assert [(s.heading, s.text) for s in out] == [
        ("Title", "intro"),
        ("Setup", "step one"),
        ("Usage", "run it"),
    ]


def test_markdown_ignores_headings_in_code_fences():
    md = b"# Real\ntext\n```\n# not a heading\n```\n"
    out = parse_file("r.md", md)
    assert len(out) == 1 and out[0].heading == "Real"
    assert "# not a heading" in out[0].text


def test_html_strips_boilerplate_and_keeps_headings():
    html = b"""<html><body><nav>MENU</nav><script>evil()</script>
    <main><h1>Guide</h1><p>Hello <b>world</b></p><h2>Next</h2><ul><li>item</li></ul></main>
    <footer>copyright</footer></body></html>"""
    out = parse_file("p.html", html)
    texts = [(s.heading, s.text) for s in out]
    assert texts == [("Guide", "Hello world"), ("Next", "item")]


def test_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFormat):
        parse_file("x.exe", b"abc")


def test_rejects_binary_and_bad_encoding():
    with pytest.raises(MalformedFile):
        parse_file("a.txt", b"abc\x00def")
    with pytest.raises(MalformedFile):
        parse_file("a.txt", b"\xff\xfe\xfa")


def test_markdown_strips_mkdocs_noise():
    from app.parsers.markdown import parse_markdown

    md = (
        "# First Steps { #first-steps }\n\n"
        "{* ../../docs_src/x.py *}\n\n"
        "/// tip\n\nUse the thing.\n\n///\n\n"
        "```\n/// keep this\n{* and this *}\n```\n"
    )
    secs = parse_markdown(md, "a.md")
    assert secs[0].heading == "First Steps"
    text = secs[0].text
    assert "Use the thing." in text and "docs_src" not in text and "/// tip" not in text
    assert "/// keep this" in text and "{* and this *}" in text
