"""DOCX parser (python-docx): headings from styles, body order preserved, tables as one section each."""
import io
import zipfile

from app import config
from app.models import ParsedSection
from app.parsers.errors import MalformedFile


def _clean(text: str) -> str:
    return " ".join(text.split())


def _table_text(table) -> str:
    rows = []
    for row in table.rows:
        cells, seen = [], set()
        for cell in row.cells:
            if id(cell._tc) in seen:  # merged cells repeat the same underlying cell
                continue
            seen.add(id(cell._tc))
            cells.append(_clean(cell.text))
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _check_zip(raw: bytes) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise MalformedFile("File is not a valid .docx (not a zip archive)") from exc
    with zf:
        infos = zf.infolist()
        if "word/document.xml" not in {i.filename for i in infos}:
            raise MalformedFile("File is not a valid .docx (word/document.xml missing)")
        total = sum(i.file_size for i in infos)
        if total > config.MAX_DOCX_UNCOMPRESSED_BYTES:
            raise MalformedFile(
                f"DOCX expands to {total // (1024 * 1024)} MB uncompressed; limit is "
                f"{config.MAX_DOCX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB"
            )


def parse_docx(raw: bytes, source: str) -> list[ParsedSection]:
    _check_zip(raw)
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        doc = Document(io.BytesIO(raw))
    except Exception as exc:
        raise MalformedFile(f"Could not read DOCX: {exc}") from exc

    sections: list[ParsedSection] = []
    heading: str | None = None
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            text = _clean(para.text)
            if not text:
                continue
            style = (para.style.name if para.style is not None else "") or ""
            if style.startswith("Heading") or style == "Title":
                heading = text
                continue
            sections.append(ParsedSection(text=text, page=None, heading=heading, source=source))
        elif tag == "tbl":
            text = _table_text(Table(child, doc))
            if text:
                sections.append(ParsedSection(text=text, page=None, heading=heading, source=source))
    return sections
