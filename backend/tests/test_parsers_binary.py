import pytest

pytest.importorskip("pdfplumber")
pytest.importorskip("docx")
pytest.importorskip("reportlab")

from app import config  # noqa: E402
from app.parsers import MalformedFile, parse_file  # noqa: E402
from tests import make_docs  # noqa: E402


def test_pdf_pages_headings_and_tables():
    secs = parse_file("guide.pdf", make_docs.make_pdf())
    assert {s.page for s in secs} == {1, 2}
    assert all(s.source == "guide.pdf" for s in secs)

    intro = next(s for s in secs if s.text.startswith("Orbit runs"))
    assert intro.heading == "Installation Guide" and intro.page == 1

    table = next(s for s in secs if "RAM | 2 GB" in s.text)
    assert table.heading == "Requirements" and table.page == 1
    assert "Disk | 10 GB" in table.text
    # table text must not also appear as ordinary paragraph text
    assert sum("2 GB" in s.text for s in secs) == 1

    # heading carries across the page break until a new heading appears
    cont = next(s for s in secs if s.text.startswith("Troubleshooting continues"))
    assert cont.page == 2 and cont.heading == "Requirements"
    support = next(s for s in secs if s.text.startswith("Contact the support"))
    assert support.heading == "Support"
    # heading lines themselves are not body text
    assert not any(s.text in ("Requirements", "Support") for s in secs)


def test_scanned_pdf_returns_no_sections():
    assert parse_file("scan.pdf", make_docs.make_pdf(blank_page=True)) == []


def test_not_a_pdf_and_corrupt_pdf():
    with pytest.raises(MalformedFile):
        parse_file("x.pdf", b"hello world")
    with pytest.raises(MalformedFile):
        parse_file("x.pdf", b"%PDF-1.4\nthis is garbage")


def test_pdf_page_limit(monkeypatch):
    monkeypatch.setattr(config, "MAX_PDF_PAGES", 1)
    with pytest.raises(MalformedFile, match="pages"):
        parse_file("guide.pdf", make_docs.make_pdf())


def test_docx_order_headings_tables():
    secs = parse_file("hb.docx", make_docs.make_docx())
    texts = [s.text for s in secs]
    assert texts[0] == "Orbit schedules jobs."
    assert secs[0].heading == "Orbit Handbook" and secs[0].page is None
    table = secs[1]
    assert table.heading == "Limits" and table.text == "Plan | Jobs\nFree | 100"
    assert texts[2] == "Limits reset monthly."
    assert texts[3] == "Merged | Solo"
    joined = " ".join(texts)
    assert "HEADER TEXT" not in joined and "FOOTER TEXT" not in joined


def test_docx_rejects_bad_files(monkeypatch):
    with pytest.raises(MalformedFile):
        parse_file("x.docx", b"not a zip")
    with pytest.raises(MalformedFile, match="document.xml"):
        parse_file("x.docx", make_docs.make_zip_without_document_xml())
    monkeypatch.setattr(config, "MAX_DOCX_UNCOMPRESSED_BYTES", 1024 * 1024)
    with pytest.raises(MalformedFile, match="uncompressed"):
        parse_file("x.docx", make_docs.make_zip_bomb_docx())


def test_pdf_running_headers_and_page_numbers_are_dropped():
    secs = parse_file("hb.pdf", make_docs.make_pdf_with_running_header())
    text = " ".join(s.text for s in secs)
    assert "ACME Handbook" not in text and "Page 3" not in text
    assert all(f"Unique body sentence number {n}" in text for n in range(1, 7))
    assert {s.page for s in secs} == set(range(1, 7))


def test_pdf_short_documents_keep_their_header_lines():
    # With fewer than 4 pages there is not enough evidence that a repeated line is a running header.
    secs = parse_file("hb.pdf", make_docs.make_pdf_with_running_header(pages=2))
    assert "ACME Handbook" in " ".join(s.text for s in secs)


def test_pdf_small_caps_heading_stays_on_one_line():
    secs = parse_file("caps.pdf", make_docs.make_pdf_small_caps_heading())
    assert secs and all(s.heading == "GOVERN" for s in secs)


def test_figure_and_table_captions_are_not_headings():
    from app.parsers.pdf import _is_caption

    assert all(_is_caption(t) for t in ["Fig. 3. Steps for creating", "Figure 2: Overview", "Table 1 Categories", "TABLE 4. x"])
    assert not any(_is_caption(t) for t in ["Figure skating", "Tables and chairs", "1. Introduction", "Fig"])
