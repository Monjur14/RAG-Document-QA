import re

from app.models import ParsedSection

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^(```|~~~)")


def parse_markdown(content: str, source: str) -> list[ParsedSection]:
    """One section per heading block. Headings inside code fences are ignored."""
    sections: list[ParsedSection] = []
    heading: str | None = None
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            sections.append(ParsedSection(text=text, heading=heading, source=source))
        buf.clear()

    for line in content.replace("\r\n", "\n").split("\n"):
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush()
            heading = m.group(2)
        else:
            buf.append(line)
    flush()
    return sections
