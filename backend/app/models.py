from pydantic import BaseModel


class ParsedSection(BaseModel):
    """Normalized output of every parser. Chunking only ever sees this."""

    text: str
    page: int | None = None      # None for formats without pages
    heading: str | None = None   # nearest section heading
    source: str                  # original file name


class UploadResponse(BaseModel):
    filename: str
    file_type: str
    sections: int
    characters: int
    preview: list[ParsedSection]
