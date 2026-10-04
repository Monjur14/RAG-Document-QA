from bs4 import BeautifulSoup

from app.models import ParsedSection

# Boilerplate and non-visible content to strip before extracting text.
_STRIP_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe"]
_BLOCK_TAGS = ["p", "li", "pre", "blockquote", "td", "th"]


def parse_html(content: str, source: str) -> list[ParsedSection]:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(_STRIP_TAGS):
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
