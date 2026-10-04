import re

from app.models import ParsedSection

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^(```|~~~)")
# MkDocs-style extras that are noise for retrieval: heading anchors "{ #id }", code-include lines
# "{* file.py *}", and admonition fences "/// tip" ... "///".
_ANCHOR = re.compile(r"\s*\{\s*#[^}]*\}\s*$")
_CODE_INCLUDE = re.compile(r"^\{\*.*\*\}\s*$")
_ADMONITION = re.compile(r"^///(\s*\w[\w-]*.*)?$")


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
            heading = _ANCHOR.sub("", m.group(2)) or m.group(2)
        elif not in_fence and (_CODE_INCLUDE.match(line.strip()) or _ADMONITION.match(line.strip())):
            continue
        else:
            buf.append(line)
    flush()
    return sections
