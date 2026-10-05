from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ParsedSection(BaseModel):
    """Normalized output of every parser. Chunking only ever sees this."""

    text: str
    page: int | None = None      # None for formats without pages
    heading: str | None = None   # nearest section heading
    source: str                  # original file name


class UploadResponse(BaseModel):
    document_id: int
    filename: str
    file_type: str
    status: str
    sections: int
    chunks: int
    characters: int
    preview: list[ParsedSection]
    quarantined: int = 0          # chunks held back from search because they look like instructions
    sanitized: int = 0            # chunks kept after an injected paragraph was cut out
    flags: list[str] = []


class DocumentInfo(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    error: str | None
    created_at: datetime
    chunk_count: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    k: int = Field(5, ge=1, le=20)
    mode: Literal["vector", "keyword", "hybrid"] = "hybrid"
    file_types: list[str] | None = None
    document_ids: list[int] | None = None


class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    chunk_index: int
    source: str
    heading: str | None
    page: int | None
    text: str
    score: float
    vector_score: float | None
    vector_rank: int | None
    keyword_rank: int | None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    k: int = Field(5, ge=1, le=10)
    mode: Literal["vector", "keyword", "hybrid"] = "hybrid"
    file_types: list[str] | None = None
    document_ids: list[int] | None = None


class CitationOut(BaseModel):
    index: int
    chunk_id: int
    document_id: int
    source: str
    heading: str | None
    page: int | None
    text: str


class AskResponse(BaseModel):
    question: str
    answer: str
    status: Literal["answered", "insufficient_evidence", "model_declined", "uncited", "blocked"]
    citations: list[CitationOut]
    confidence: float | None
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float
    retrieved: int
    cache: Literal["miss", "exact", "semantic"] = "miss"
    flags: list[str] = []
