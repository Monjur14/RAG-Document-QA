from app.models import ParsedSection


def parse_txt(content: str, source: str) -> list[ParsedSection]:
    """Split plain text into paragraph-group sections (blank-line separated)."""
    paragraphs = [p.strip() for p in content.replace("\r\n", "\n").split("\n\n")]
    return [ParsedSection(text=p, source=source) for p in paragraphs if p]
