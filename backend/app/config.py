import os
from pathlib import Path

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))

# Formats currently supported. PDF/DOCX arrive in Week 2.
ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm"}

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rag:rag@localhost:5433/rag")
# Must match the embedding model (bge-large-en-v1.5 = 1024). Changing it needs a migration + re-index.
EMBEDDING_DIM = 1024

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
