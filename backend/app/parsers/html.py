import re

from bs4 import BeautifulSoup

from app.models import ParsedSection

# Boilerplate and non-visible content to strip before extracting text.
_STRIP_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe"]
_BLOCK_TAGS = ["p", "li", "pre", "blockquote", "td", "th"]
# Text a human reader cannot see is a classic hiding place for injected instructions.
_HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?:\.0+)?\s*(?:px|pt|em|rem|%)?\s*(?:;|$)|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$)",
    re.I)


def parse_html(content: str, source: str) -> list[ParsedSection]:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        if getattr(tag, "decomposed", False) or tag.attrs is None:
            continue
        if tag.has_attr("hidden") or _HIDDEN_STYLE.search(tag.get("style") or ""):
            tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    sections: list[ParsedSection] = []
    heading: str | None = None

    for el in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", *_BLOCK_TAGS]):
        text = " ".join(el.get_text(" ", strip=True).split())
        if not text:
            continue
        if el.name.startswith("h") and len(el.name) == 2:
            heading = text
            continue
        # Skip nested blocks already captured by a parent block (e.g. <li><p>)
        if el.find_parent(_BLOCK_TAGS):
            continue
        sections.append(ParsedSection(text=text, heading=heading, source=source))
    return sections
