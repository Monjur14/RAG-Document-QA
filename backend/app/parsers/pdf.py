"""PDF parser (pdfplumber, MIT). Keeps page numbers, detects headings by font size/weight,
and emits each ruled table as its own section. Scanned PDFs (no text layer) return []."""
import io
import re
from collections import Counter
from dataclasses import dataclass

from app import config
from app.models import ParsedSection
from app.parsers.errors import MalformedFile

LINE_TOLERANCE = 3.0       # points: words whose baselines differ less than this share a line
HEADING_SIZE_RATIO = 1.15  # heading if font size >= body size * this
HEADER_FOOTER_BAND = 0.08  # top/bottom fraction of the page where repeating lines count as running headers
PARAGRAPH_GAP_RATIO = 0.6  # vertical gap above this * line height starts a new paragraph
WORD_GAP_RATIO = 0.1       # word gap as a fraction of font size; the fixed default glues words in some PDFs


@dataclass
class _Line:
    text: str
    size: float
    bold: bool
    top: float
    bottom: float


def _in_any(bboxes, x0, x1, top, bottom) -> bool:
    cx, cy = (x0 + x1) / 2, (top + bottom) / 2
    return any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b in bboxes)


def _merge_small_caps(group: list[dict]) -> list[dict]:
    """Join a larger capital with the smaller capitals that follow it on the same baseline: 'G' + 'OVERN'
    is one word set in small caps, not two."""
    out: list[dict] = []
    for w in group:
        prev = out[-1] if out else None
        if (
            prev is not None
            and len(prev["text"]) == 1 and prev["text"].isupper()
            and w["text"].isupper() and w["size"] < prev["size"] - 0.5
            and 0 <= w["x0"] - prev["x1"] < 0.6 * prev["size"]
        ):
            out[-1] = {**prev, "text": prev["text"] + w["text"], "x1": w["x1"],
                       "size": max(prev["size"], w["size"]), "top": min(prev["top"], w["top"]),
                       "bottom": max(prev["bottom"], w["bottom"])}
        else:
            out.append(w)
    return out


def _group_lines(words: list[dict]) -> list[_Line]:
    # Group by baseline (bottom), not top: in small-caps or drop-cap text ("G" + "OVERN") the letters have
    # different sizes, so their tops differ even though they sit on one line.
    words = sorted(words, key=lambda w: (w["bottom"], w["x0"]))
    groups: list[list[dict]] = []
    for w in words:
        if groups and abs(w["bottom"] - groups[-1][0]["bottom"]) <= LINE_TOLERANCE:
            groups[-1].append(w)
        else:
            groups.append([w])
    lines = []
    for g in groups:
        g.sort(key=lambda w: w["x0"])
        g = _merge_small_caps(g)
        text = " ".join(w["text"] for w in g).strip()
        if not text:
            continue
        lines.append(
            _Line(
                text=text,
                size=round(max(w["size"] for w in g), 1),
                bold=all("bold" in w["fontname"].lower() for w in g),
                top=min(w["top"] for w in g),
                bottom=max(w["bottom"] for w in g),
            )
        )
    return lines


def _table_text(rows) -> str:
    out = []
    for row in rows:
        cells = [" ".join((c or "").split()) for c in row]
        if any(cells):
            out.append(" | ".join(cells))
    return "\n".join(out)


_CAPTION = re.compile(r"^(fig\.?|figure|table)\s*\d+[.:]?\s", re.IGNORECASE)


def _is_caption(text: str) -> bool:
    """'Fig. 3. Steps ...' / 'Table 2 ...' are captions, not section headings: they must not replace the
    real heading that the following paragraphs belong to."""
    return bool(_CAPTION.match(text))


def _signature(text: str) -> str:
    """Line text with digits masked, so 'Page 3' and 'Page 4' count as the same running line."""
    return "".join("#" if c.isdigit() else c for c in " ".join(text.split()).lower())


def _in_band(ln: "_Line", height: float) -> bool:
    return ln.bottom <= height * HEADER_FOOTER_BAND * 1.5 or ln.top >= height * (1 - HEADER_FOOTER_BAND)


def _repeating_header_footer_lines(raw_pages) -> set[str]:
    """Signatures of lines that sit in the top/bottom band on many pages (running headers, page numbers)."""
    if len(raw_pages) < 4:
        return set()
    counts: Counter = Counter()
    for _, height, lines, _ in raw_pages:
        counts.update({_signature(ln.text) for ln in lines if _in_band(ln, height)})
    need = max(3, int(len(raw_pages) * 0.3))
    return {sig for sig, n in counts.items() if n >= need}


def _is_running_line(ln: "_Line", height: float, repeated: set[str]) -> bool:
    return bool(repeated) and _in_band(ln, height) and _signature(ln.text) in repeated


def _join(lines: list[str]) -> str:
    text = ""
    for ln in lines:
        if not text:
            text = ln
        elif len(text) > 1 and text.endswith("-") and text[-2].isalpha() and ln[:1].islower():
            text = text[:-1] + ln  # de-hyphenate a word broken across lines
        else:
            text += " " + ln
    return text


def parse_pdf(raw: bytes, source: str) -> list[ParsedSection]:
    if b"%PDF-" not in raw[:1024]:
        raise MalformedFile("File is not a valid PDF (missing %PDF header)")
    import pdfplumber

    try:
        pdf = pdfplumber.open(io.BytesIO(raw))
    except Exception as exc:
        if "password" in type(exc).__name__.lower() or "password" in str(exc).lower():
            raise MalformedFile("PDF is password-protected") from exc
        raise MalformedFile(f"Could not read PDF: {exc or type(exc).__name__}") from exc

    with pdf:
        if len(pdf.pages) > config.MAX_PDF_PAGES:
            raise MalformedFile(f"PDF has {len(pdf.pages)} pages; limit is {config.MAX_PDF_PAGES}")
        raw_pages: list[tuple[int, float, list[_Line], list]] = []
        try:
            for number, page in enumerate(pdf.pages, start=1):
                tables = page.find_tables()
                bboxes = [t.bbox for t in tables]
                view = page
                if bboxes:
                    view = page.filter(
                        lambda o, bb=bboxes: o.get("object_type") != "char"
                        or not _in_any(bb, o["x0"], o["x1"], o["top"], o["bottom"])
                    )
                words = view.extract_words(extra_attrs=["size", "fontname"], x_tolerance_ratio=WORD_GAP_RATIO)
                raw_pages.append((number, float(page.height), _group_lines(words), [(t.bbox[1], t.extract()) for t in tables]))
        except MalformedFile:
            raise
        except Exception as exc:
            raise MalformedFile(f"Could not extract text from PDF: {exc or type(exc).__name__}") from exc

    repeated = _repeating_header_footer_lines(raw_pages)
    pages: list[tuple[int, list[tuple[float, str, object]]]] = []
    sizes: Counter = Counter()
    bold_chars = total_chars = 0
    for number, height, lines, tables in raw_pages:
        lines = [ln for ln in lines if not _is_running_line(ln, height, repeated)]
        for ln in lines:
            sizes[ln.size] += len(ln.text)
            total_chars += len(ln.text)
            if ln.bold:
                bold_chars += len(ln.text)
        items = [(ln.top, "line", ln) for ln in lines] + [(top, "table", rows) for top, rows in tables]
        items.sort(key=lambda i: i[0])
        pages.append((number, items))

    if not sizes:
        body = 0.0
    else:
        body = sizes.most_common(1)[0][0]
    mostly_bold = total_chars > 0 and bold_chars / total_chars > 0.5

    def is_heading(ln: _Line) -> bool:
        if _is_caption(ln.text):
            return False
        if body and ln.size >= body * HEADING_SIZE_RATIO:
            return True
        return ln.bold and not mostly_bold and len(ln.text) <= 80 and not ln.text.endswith(".")

    sections: list[ParsedSection] = []
    heading: str | None = None
    for number, items in pages:
        para: list[str] = []
        prev: _Line | None = None
        heading_buf: list[str] = []

        def flush_para():
            nonlocal para
            if para:
                sections.append(
                    ParsedSection(text=_join(para), page=number, heading=heading, source=source)
                )
                para = []

        def flush_heading():
            nonlocal heading, heading_buf
            if heading_buf:
                heading = " ".join(heading_buf)
                heading_buf = []

        for _, kind, obj in items:
            if kind == "table":
                flush_heading()
                flush_para()
                text = _table_text(obj)
                if text:
                    sections.append(ParsedSection(text=text, page=number, heading=heading, source=source))
                prev = None
                continue
            ln: _Line = obj
            if is_heading(ln):
                flush_para()
                heading_buf.append(ln.text)
            else:
                flush_heading()
                height = max(ln.bottom - ln.top, 1.0)
                if prev is not None and ln.top - prev.bottom > PARAGRAPH_GAP_RATIO * height:
                    flush_para()
                para.append(ln.text)
            prev = ln
        flush_heading()
        flush_para()
    return sections
