from pathlib import Path

from app.models import ParsedSection
from app.parsers.docx import parse_docx
from app.parsers.errors import MalformedFile, UnsupportedFormat
from app.parsers.html import parse_html
from app.parsers.markdown import parse_markdown
from app.parsers.pdf import parse_pdf
from app.parsers.text import parse_txt

_TEXT_PARSERS = {
    ".txt": parse_txt,
    ".md": parse_markdown,
    ".markdown": parse_markdown,
    ".html": parse_html,
    ".htm": parse_html,
}


# Binary formats take raw bytes; pdf/docx libraries are imported lazily inside the parsers.
_BINARY_PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
}

__all__ = ["MalformedFile", "UnsupportedFormat", "decode_text", "parse_file"]


def decode_text(raw: bytes) -> str:
    """Decode bytes as UTF-8 text; reject binary content masquerading as text."""
    if b"\x00" in raw:
        raise MalformedFile("File contains null bytes; not a text document")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MalformedFile("File is not valid UTF-8 text") from exc


def parse_file(filename: str, raw: bytes) -> list[ParsedSection]:
    """Single entry point for parsing. Can later run in a sandboxed subprocess."""
    ext = Path(filename).suffix.lower()
    binary = _BINARY_PARSERS.get(ext)
    if binary is not None:
        return binary(raw, filename)
    parser = _TEXT_PARSERS.get(ext)
    if parser is None:
        raise UnsupportedFormat(f"Unsupported file type: {ext or '(none)'}")
    return parser(decode_text(raw), filename)
