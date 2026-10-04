import os
from pathlib import Path

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))

# Formats currently supported. PDF/DOCX arrive in Week 2.
ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm"}
