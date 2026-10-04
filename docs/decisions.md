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

## 2026-10-04: Embeddings and ingestion
- **Model: BAAI/bge-small-en-v1.5 (384-d), run on the GPU via sentence-transformers.** Small and fast, strong on retrieval benchmarks, and free/local. Bigger bge models are a candidate to compare in the evals (needs a migration: the column size is fixed).
- **Query/passage asymmetry:** bge expects an instruction prefix on queries but not on passages, so `embed_query` and `embed_documents` are separate methods.
- **Chunk heading is prepended to the text that gets embedded** (not to the stored text), so a passage like "Run the thing." is embedded with its section context. Worth ablating in the evals.
- **Vectors are L2-normalized**, so cosine distance and dot product agree.
- **Embedder is an interface** (`Embedder` protocol) with lazy model loading; tests use a deterministic hash-based fake, so the suite needs no GPU or model download. One slow test with the real model runs with `RUN_MODEL_TESTS=1`.
- **Document row is committed as `pending` before embedding.** If embedding/storage fails, the transaction is rolled back and the document is marked `failed` with the reason, so failures are visible in the library and never leave half-indexed documents.
- **Parse/validation errors are rejected before any database write** and return 4xx; only indexing failures create a `failed` record.
- **Blocking work (parsing, embedding, SQL) runs in a threadpool** so the async API stays responsive.
- Original upload files are not stored yet; re-index will need that (library page work, later).

## 2026-10-04: Embedding model changed to bge-large-en-v1.5 (1024-d)
- Supersedes the bge-small choice above. Picked for the best retrieval quality of the bge English family; the RTX 5070 Ti handles it comfortably, and the cost is slower indexing/queries and a larger index (1024 vs 384 dimensions per chunk).
- Done as migration `0002` (drops the HNSW index, resizes the column, rebuilds the index). It deletes existing documents because vectors from different models can't be converted; fine with test data only.
- pgvector's HNSW index supports up to 2000 dimensions, so 1024 is within limits.
- Still to measure in the evals: bge-small vs bge-base vs bge-large (quality gain vs latency), so the choice is backed by numbers.

## 2026-10-04: Retrieval
- **Three modes behind one `search()`**: vector, keyword, hybrid, so the evals can compare them directly.
- **Hybrid uses reciprocal rank fusion (k=60) over the top 50 of each retriever.** RRF uses only ranks, so cosine similarity and `ts_rank` never need to be normalised to the same scale.
- **Keyword queries are OR-joined** (`word | word | ...`) instead of `websearch_to_tsquery`'s AND. A natural-language question rarely contains every word of the answer passage, and stop words are dropped by Postgres. The query is built from letters/digits only, so user text can't inject tsquery syntax.
- **Cosine similarity is kept on every hit (`vector_score`)**, including in hybrid mode: the "I don't know" threshold in step 5 needs it, because RRF scores say nothing about absolute relevance.
- **Only `indexed` documents are searchable**; pending/failed documents never leak into answers.
- **Seed eval (16 questions, 3 sample docs)** exists to prove the harness and give a first signal; it is too small to support claims. The 80-question set comes in Week 2.
