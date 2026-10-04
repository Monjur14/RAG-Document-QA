# Decision log

Short record of trade-offs and why. Newest at the bottom.

## 2026-10-04: Project start
- **Stack:** Python + FastAPI, PostgreSQL + pgvector, local embeddings, Ollama for dev LLM. Chosen to run at $0.
- **Parsers return one normalized structure** (`ParsedSection`: text, page, heading, source) so chunking/retrieval never care about file format.
- **Upload validation by extension + size + content sniffing** (no binary bytes in text formats), not extension alone.
- **Parsing is isolated behind `parse_file()`** so it can later move into a sandboxed subprocess (Week 4 security work) without API changes.

## 2026-10-04: Chunking
- **Two strategies behind one config** (`fixed`, `heading`) so the evals can compare them directly.
- **Heading-aware chunks never cross a heading or page boundary.** This keeps citations accurate (one heading, one page per chunk).
- **Overlap is applied only when a single block must be split.** Packing whole paragraphs already preserves sentence context, so extra overlap between packed chunks would mostly duplicate text.
- **Sizes are in characters (default 800/100), not tokens.** Simple and model-independent for now; revisit if evals show a problem.

## 2026-10-04: Database layer
- **One `chunks` table holds text, metadata, vector and keyword column.** Hybrid search then needs no joins; both indexes sit on the same rows.
- **`tsv` is a generated column**, so Postgres keeps keyword search in sync with the text and application code can't forget to update it.
- **HNSW with cosine distance** (`vector_cosine_ops`). Chosen over IVFFlat because it needs no training step and has better recall; the exact-vs-HNSW comparison is planned for the evals.
- **Embedding size fixed at 384** (bge-small-en-v1.5). Switching models means changing the column and re-indexing.
- **Raw SQL via psycopg 3, no ORM.** The queries are few and performance-sensitive, and plain SQL is easier to explain in interviews.
- **Repository functions take a connection and never commit**, so ingestion can be one transaction: a failed upload leaves no half-indexed document.
- **DB tests skip when Postgres is unavailable** and roll back after each test, so `pytest` still works without Docker.

## 2026-10-04: Migrations (working rule)
- **Every schema change is an Alembic migration** in `backend/migrations/versions/`; the schema is never edited by hand and there is no standalone schema file. `alembic upgrade head` recreates the full database from an empty one.
- **Migrations are plain SQL (`op.execute`), no ORM models.** Matches the raw-SQL decision and lets us use pgvector, HNSW and generated columns directly.
- **Every migration has a working `downgrade`.** A test runs up, down, up on a throwaway database, so a broken migration is caught by `pytest`.
- Replaced `schema.sql` with migration `0001`.

## 2026-10-04: Host port 5433 for Postgres
- The Docker database is published on host port **5433**, not 5432, to avoid clashing with a PostgreSQL already installed on the developer's machine (which caused "password authentication failed"). Inside the container it is still 5432.
