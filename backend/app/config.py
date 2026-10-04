import os
from pathlib import Path

from dotenv import load_dotenv

# Read settings from the repo-root .env if present (real environment variables win).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))

# Formats currently supported. PDF/DOCX arrive in Week 2.
ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm"}

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rag:rag@localhost:5433/rag")
# Fail fast (instead of hanging) when the database is down, e.g. Docker not running.
DB_CONNECT_TIMEOUT_S = int(os.getenv("DB_CONNECT_TIMEOUT_S", "5"))
# Must match the embedding model (bge-large-en-v1.5 = 1024). Changing it needs a migration + re-index.
EMBEDDING_DIM = 1024

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")

# --- LLM (answer generation) ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
# Qwen3-style "thinking" models: set OLLAMA_THINK=false to skip the slow reasoning phase. Unset = don't send it.
OLLAMA_THINK = {"true": True, "false": False}.get(os.getenv("OLLAMA_THINK", "").strip().lower())
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "120"))

# --- answering ---
ANSWER_TOP_K = int(os.getenv("ANSWER_TOP_K", "5"))
# Refuse without calling the LLM when the best chunk's cosine similarity is below this.
# Calibrated on the 16+8 question seed set with bge-large: lowest answerable best-score 0.505,
# highest off-topic 0.459 -> midpoint 0.48. Tiny sample: recalibrate on the full eval sets in Week 2,
# and whenever the embedding model changes (scores are not comparable across models).
# Run `python -m evals.threshold_eval` to re-measure.
MIN_VECTOR_SCORE = float(os.getenv("MIN_VECTOR_SCORE", "0.48"))
