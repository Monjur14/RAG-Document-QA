from pathlib import Path

from app.models import ParsedSection
from app.parsers.html import parse_html
from app.parsers.markdown import parse_markdown
from app.parsers.text import parse_txt

_PARSERS = {
    ".txt": parse_txt,
    ".md": parse_markdown,
    ".markdown": parse_markdown,
    ".html": parse_html,
    ".htm": parse_html,
}


class UnsupportedFormat(ValueError):
    pass


class MalformedFile(ValueError):
    pass


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
    parser = _PARSERS.get(ext)
    if parser is None:
        raise UnsupportedFormat(f"Unsupported file type: {ext or '(none)'}")
    return parser(decode_text(raw), filename)
