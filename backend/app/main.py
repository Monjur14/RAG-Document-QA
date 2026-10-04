from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB
from app.models import UploadResponse
from app.parsers import MalformedFile, UnsupportedFormat, parse_file

app = FastAPI(title="Secure RAG Document Q&A")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile) -> UploadResponse:
    # Use only the base name; never trust client-supplied paths.
    filename = Path(file.filename or "").name
    ext = Path(filename).suffix.lower()
    if not filename or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Unsupported file type. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    # Read at most limit+1 bytes so oversized uploads are rejected without loading them fully.
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")
    if not raw:
        raise HTTPException(400, "File is empty")

    try:
        sections = parse_file(filename, raw)
    except UnsupportedFormat as exc:
        raise HTTPException(415, str(exc)) from exc
    except MalformedFile as exc:
        raise HTTPException(422, str(exc)) from exc

    if not sections:
        raise HTTPException(422, "No extractable text found in file")

    return UploadResponse(
        filename=filename,
        file_type=ext.lstrip("."),
        sections=len(sections),
        characters=sum(len(s.text) for s in sections),
        preview=sections[:3],
    )
