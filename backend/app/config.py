import os
from pathlib import Path

from dotenv import load_dotenv

# Read settings from the repo-root .env if present (real environment variables win).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))

ALLOWED_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".pdf", ".docx"}
# Parser safety limits (read at call time so tests can override them).
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "500"))
MAX_DOCX_UNCOMPRESSED_BYTES = int(os.getenv("MAX_DOCX_UNCOMPRESSED_MB", "100")) * 1024 * 1024

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rag:rag@localhost:5433/rag")
# Fail fast (instead of hanging) when the database is down, e.g. Docker not running.
DB_CONNECT_TIMEOUT_S = int(os.getenv("DB_CONNECT_TIMEOUT_S", "5"))
# Must match the embedding model (bge-large-en-v1.5 = 1024). Changing it needs a migration + re-index.
EMBEDDING_DIM = 1024

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
# Cross-encoder used to rerank retrieval candidates (see app/rerank.py).
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
# /ask reorders the retrieved candidates with the cross-encoder (adds ~1 GB of model memory and ~80 ms).
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
SEMANTIC_CACHE_THRESHOLD = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.95"))  # cosine; high = only near-identical wording
RERANK_POOL = int(os.getenv("RERANK_POOL", "20"))

# --- LLM (answer generation) ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
# Qwen3-style "thinking" models: set OLLAMA_THINK=false to skip the slow reasoning phase. Unset = don't send it.
OLLAMA_THINK = {"true": True, "false": False}.get(os.getenv("OLLAMA_THINK", "").strip().lower())
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "120"))
# Which LLM answers. LLM_PROVIDERS="auto" (default) uses every provider that has a key, in this order:
#   OpenAI -> Gemini -> OpenRouter -> local Ollama (always last, needs no key)
# So: an OpenAI key present -> OpenAI; else a Gemini key -> Gemini; no keys at all -> local Ollama. If a hosted
# provider fails, the next one in the list answers. To force a specific chain, list names, e.g. LLM_PROVIDERS=gemini,ollama
# API keys belong in the repo-root .env (git-ignored) or the server's environment: never in the repo, frontend or logs.
LLM_PROVIDERS = os.getenv("LLM_PROVIDERS", "auto")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")        # model names and prices change: check OpenAI's pricing page
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")   # model names change: check Google's current list
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))       # extra tries per provider on connection errors / 429 / 5xx
LLM_BACKOFF_S = float(os.getenv("LLM_BACKOFF_S", "0.5"))       # wait 0.5 s, then 1 s, ...
LLM_COOLDOWN_S = float(os.getenv("LLM_COOLDOWN_S", "30"))      # skip a provider this long after it fails

# --- answering ---
ANSWER_TOP_K = int(os.getenv("ANSWER_TOP_K", "5"))
# Refuse without calling the LLM when the best chunk's cosine similarity is below this.
# Calibrated on the 16+8 question seed set with bge-large: lowest answerable best-score 0.505,
# highest off-topic 0.459 -> midpoint 0.48. Tiny sample: recalibrate on the full eval sets in Week 2,
# and whenever the embedding model changes (scores are not comparable across models).
# Run `python -m evals.threshold_eval` to re-measure.
MIN_VECTOR_SCORE = float(os.getenv("MIN_VECTOR_SCORE", "0.48"))
