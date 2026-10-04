"""Chunking: turn normalized ParsedSections into retrieval-sized Chunks.

Two strategies so they can be compared in the evals:
- "fixed":   ignores document structure; sliding window over the whole text.
- "heading": never crosses a heading/page boundary; packs paragraphs up to
             chunk_size and only splits (with overlap) a block that is too big.
"""
from bisect import bisect_right
from typing import Literal

from pydantic import BaseModel, model_validator

from app.models import ParsedSection


class ChunkConfig(BaseModel):
    strategy: Literal["fixed", "heading"] = "heading"
    chunk_size: int = 800   # max characters per chunk
    overlap: int = 100      # characters shared between neighbouring windows

    @model_validator(mode="after")
    def _check(self) -> "ChunkConfig":
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if not 0 <= self.overlap < self.chunk_size:
            raise ValueError("overlap must be >= 0 and < chunk_size")
        return self


class Chunk(BaseModel):
    text: str
    chunk_index: int
    source: str
    heading: str | None = None
    page: int | None = None


def _split_text(text: str, size: int, overlap: int) -> list[tuple[int, str]]:
    """Sliding window over text. Returns (start_offset, piece); cuts at whitespace."""
    pieces: list[tuple[int, str]] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + size, n)
        if end < n:
            # Prefer to cut at whitespace in the back half of the window.
            cut = max(text.rfind(" ", start, end), text.rfind("\n", start, end))
            if cut > start + size // 2:
                end = cut
        raw = text[start:end]
        piece = raw.strip()
        if piece:
            pieces.append((start + (len(raw) - len(raw.lstrip())), piece))
        if end >= n:
            break
        nxt = end - overlap
        if nxt <= start:
            nxt = end
        # Don't start the next window in the middle of a word.
        while 0 < nxt < end and not text[nxt - 1].isspace():
            nxt += 1
        start = nxt
    return pieces


def _chunk_fixed(sections: list[ParsedSection], cfg: ChunkConfig) -> list[Chunk]:
    if not sections:
        return []
    text = ""
    starts: list[int] = []
    for s in sections:
        starts.append(len(text))
        text += s.text + "\n\n"

    chunks: list[Chunk] = []
    for offset, piece in _split_text(text, cfg.chunk_size, cfg.overlap):
        sec = sections[bisect_right(starts, offset) - 1]  # section where the chunk starts
        chunks.append(Chunk(text=piece, chunk_index=0, source=sec.source,
                            heading=sec.heading, page=sec.page))
    return chunks


def _chunk_heading(sections: list[ParsedSection], cfg: ChunkConfig) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[str] = []
    key: tuple | None = None

    def emit(text: str) -> None:
        chunks.append(Chunk(text=text, chunk_index=0, source=key[0],
                            heading=key[1], page=key[2]))

    def flush() -> None:
        if buf:
            emit("\n\n".join(buf))
            buf.clear()

    for s in sections:
        k = (s.source, s.heading, s.page)
        if k != key:           # new heading/page/file: start a fresh chunk
            flush()
            key = k
        if len(s.text) > cfg.chunk_size:   # oversized block: split with overlap
            flush()
            for _, piece in _split_text(s.text, cfg.chunk_size, cfg.overlap):
                emit(piece)
            continue
        if buf and len("\n\n".join([*buf, s.text])) > cfg.chunk_size:
            flush()
        buf.append(s.text)
    flush()
    return chunks


def chunk_sections(sections: list[ParsedSection], cfg: ChunkConfig | None = None) -> list[Chunk]:
    cfg = cfg or ChunkConfig()
    chunks = _chunk_fixed(sections, cfg) if cfg.strategy == "fixed" else _chunk_heading(sections, cfg)
    for i, c in enumerate(chunks):
        c.chunk_index = i
    return chunks
