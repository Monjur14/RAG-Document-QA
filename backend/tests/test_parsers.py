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
