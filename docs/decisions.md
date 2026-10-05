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

## 2026-10-04: Answer generation
- **Provider interface** (`generate(prompt, system) -> LLMResponse`) with an Ollama adapter first; Gemini/OpenRouter adapters, retries and fallback are Week 3. Model is a setting (`OLLAMA_MODEL`, default `llama3.1:8b`), so models can be compared in the evals by changing one variable.
- **Temperature 0, explicit `num_ctx`.** Deterministic answers make eval runs repeatable; Ollama's default context is small, so it is set explicitly so the retrieved sources are not silently truncated.
- **`think` is only sent when `OLLAMA_THINK` is set** (needed for Qwen3-style models, to skip the slow reasoning phase; omitted for Llama).
- **Refuse before calling the LLM when evidence is weak** (best cosine similarity below `MIN_VECTOR_SCORE`). Saves latency and cost, and removes the chance of the model improvising from weak context. The threshold is *calibrated*, not guessed: `python -m evals.threshold_eval`.
- **Four answer statuses** (`answered`, `insufficient_evidence`, `model_declined`, `uncited`) instead of a boolean, so the UI and the evals can tell the failure modes apart. An answer with no valid `[n]` citation is flagged `uncited` rather than presented as trustworthy.
- **Citations are validated against the retrieved set**; numbers the model invents are dropped.
- **Prompt structure (first layer of injection defense):** sources are wrapped in `<source>` tags, the system prompt says they are untrusted data, and passage text/attributes are neutralized so a document cannot close the tag or add attributes. Known limitation: a literal `[1]` in a model answer that is not a citation is counted as one.
- **`.env` is now loaded automatically** (python-dotenv), so settings in the repo-root `.env` take effect.

## 2026-10-04: Refusal threshold set to 0.48 (measured, provisional)
- `python -m evals.threshold_eval` with bge-large on the seed sets: lowest answerable question scored 0.505; off-topic questions peaked at 0.459. The old guess of 0.5 kept every answerable question by a margin of only 0.005. 0.48 is the midpoint, giving about 0.02 of margin on each side.
- **On-topic questions the documents do not answer** (e.g. "How much does Orbit cost?") score 0.57-0.69, inside the range of real answers, so no threshold can refuse them. They rely on the LLM declining. This is why there are two layers (score threshold, then the model's own "I don't know") and why the answer statuses distinguish them.
- **Caveats:** only 4 off-topic and 4 on-topic unanswerable questions; the margin will shrink on a bigger set. Thresholds are specific to the embedding model: recalibrate whenever the model changes.
- Error costs are asymmetric: wrongly refusing a real question is worse than passing a weak one to the LLM (which usually declines), so when in doubt, err toward the lower threshold.

## 2026-10-04: PDF and DOCX parsers
- **pdfplumber (MIT) over PyMuPDF (AGPL).** Licensing matters for a portfolio project that may be published; pdfplumber also gives per-word font size/name and table detection. It is slower than PyMuPDF, which is acceptable for single-user uploads.
- **Heading detection is heuristic:** a line is a heading if its font is at least 1.15x the document's body size (length-weighted mode), or it is fully bold, at most 80 characters, and does not end with a period (disabled when over half the document is bold). The heading carries across page breaks until the next heading.
- **Tables** found by `find_tables()` (ruled tables) become one section each, rows joined with ` | `; their text is excluded from paragraph extraction so it is not indexed twice. Borderless tables are not detected and come out as ordinary text.
- **DOCX:** headings come from the Heading/Title styles, body order is preserved, merged cells are de-duplicated, headers and footers are skipped. DOCX has no page numbers (`page=None`).
- **Safety limits:** PDFs over `MAX_PDF_PAGES` (500) and DOCX files whose uncompressed size exceeds 100 MB (zip-bomb guard) are rejected. Real sandboxing of parsing (subprocess with limits) is deferred to the Week 4 security work.
- **Known limitations:** scanned PDFs (no text layer) are rejected with an OCR hint; a paragraph that spans a page break becomes two sections; multi-column layouts may interleave.
- **Word spacing fix (found on the real NIST AI RMF PDF):** pdfplumber's fixed 3pt word gap glued words together ("Riskmanagementrefers..."), which would have hurt both embeddings and keyword search. `extract_words` now uses `x_tolerance_ratio=0.1` (gap relative to font size). Lesson: synthetic test PDFs are not enough; always check parser output on a real document.

## 2026-10-04: First real-corpus retrieval results (32 questions, bge-large) and reranking
- Result: vector hit@1 0.66 / hit@5 0.84 / MRR 0.721; keyword 0.28 / 0.56 / 0.398; hybrid 0.53 / 0.88 / 0.660. PDFs are harder than Markdown (vector hit@1 0.42 vs 0.80).
- **Hybrid improves recall (hit@5) but hurts top-1**: the keyword list is weak (OR-joined terms over small heading-sized chunks) and RRF gives it equal weight. So hybrid is not automatically better; candidate fixes are a weighted fusion and a reranker.
- **Many "misses" are the right answer one rank down, or a different chunk that also answers** (e.g. the trustworthiness characteristics appear in both the Executive Summary and section 3). Quote-based labels are strict, so hit@1 understates quality. Treat differences of one or two questions as noise at n=32.
- **Reranking added** (`app/rerank.py`): retrieve a pool of 20, re-score with a cross-encoder (`BAAI/bge-reranker-base`, configurable via `RERANK_MODEL`), keep the top k. `vector_score` is preserved on reranked hits so the refusal threshold keeps working. `corpus_eval` now also reports `vector+rerank` and `hybrid+rerank`.
- **PDF heading quirk:** bold figure/table captions ("Fig. 3. ...") and nested headings are sometimes taken as headings. Not fixed yet.
- **Risk noted:** pgvector's HNSW index applies filters (`document_ids`) after the index scan, so filtered searches can return fewer than k rows, especially after many deletes (seen once in the test database). pgvector 0.8 has `hnsw.iterative_scan`; revisit before relying on filtered search at scale.

## 2026-10-04: Reranking measured and enabled for /ask
- Corpus eval (32 questions, bge-large, bge-reranker-base over a pool of 20): vector hit@1 0.66 -> **vector+rerank 0.81**, **hybrid+rerank 0.81 / hit@3 0.94 / hit@5 0.97 / MRR 0.878** (vector alone: 0.66 / 0.78 / 0.84 / 0.721). PDFs gained most (vector hit@1 0.42 -> 0.75). Reranking also fixed the hybrid problem: hybrid finds more candidates, the reranker orders them.
- Cost: about 80 ms per query once the model is loaded (the 27,792 ms/query printed for vector+rerank was the one-off 1 GB model download, not steady-state speed) and ~1 GB extra model memory.
- vector+rerank and hybrid+rerank differ by about one question, which is noise at n=32; hybrid+rerank is kept as the default mode because it had the best recall.
- Remaining misses are mostly label strictness (another chunk also answers, e.g. n03, n04) plus f01, f08, f11, c04. Fixing the labels or accepting any chunk that contains the evidence would raise the ceiling; more questions are needed.
- **/ask now reranks** (`RERANK_ENABLED`, default true; `RERANK_POOL`, default 20). **The refusal threshold uses the best cosine score in the whole candidate pool, not just the reranked top k**, otherwise the reranker pushing the highest-cosine chunk out of the top k could turn a good match into a refusal. Tests override the reranker so the real model is never loaded.

## 2026-10-04: PDF running headers and page numbers removed
- Found by asking a real question: a retrieved NIST chunk began with the running header "NIST AI 100-1 AI RMF 1.0", repeated on every page. A line is dropped when, with digits masked, it sits in the top or bottom 8% band on at least 30% of pages (minimum 3). PDFs under 4 pages are left alone because there is too little evidence. The NIST AI RMF went from 313 to 270 sections and the CSF from 316 to 258.
- Not a bug after all: heading text such as "Core andProfiles" seen in terminal output was line-wrapping in the console; the parsed text has the space.

## 2026-10-04: Eval contamination fixed (search only the eval's own documents)
- After removing PDF running headers the corpus eval *dropped* (hybrid+rerank hit@1 0.81 -> 0.75, PDF hit@1 0.75 -> 0.58). The cause was not the parser: a copy of the same NIST PDF had been uploaded to the dev database by hand, and its identical chunks filled the top-k slots; the eval then discarded them because they came from a different file name, leaving 1-2 hits per query. The tell was result lists shorter than k for NIST questions only.
- Fix: the eval passes `document_ids` of its own documents to every search and reports how many other documents were in the database. Lesson: an eval must not depend on the database being empty. Numbers from the run before this fix are not comparable and should not be quoted.

## 2026-10-04: Harder eval (82 questions) reverses the reranker conclusion; switch to bge-reranker-v2-m3
- On the 32 easy, word-overlap questions the base reranker looked like a big win. On the full 82 (45 paraphrased, 5 multi-passage, 20 unanswerable kept separately) it is not: vector 0.63 / 0.78 / 0.87 (hit@1/3/5), MRR 0.714; **bge-reranker-base** 0.61 / 0.79 / 0.87, MRR 0.710; hybrid+base 0.60 / 0.82 / 0.85. The base reranker helped questions that reuse the document's words (hit@1 0.69 -> 0.75) and hurt paraphrased ones (0.67 -> 0.58). Pool size (10, 20 or 40) made no difference. **The earlier "hybrid+rerank is clearly best" claim came from an eval that was too easy.**
- Things that were tested and rejected: rerank without the heading text (hit@1 0.45, much worse: the heading matters); weighted fusion giving keyword search 0.2 or 0.5 of the vector weight (0.59 / 0.56, worse than vector alone).
- **bge-reranker-v2-m3** (2.2 GB) is clearly better: vector+rerank 0.72 / 0.85 / 0.89, MRR 0.792, paraphrased 0.73 / 0.96; hybrid+rerank 0.71 / 0.83 / 0.89, MRR 0.783. It is now the default `RERANK_MODEL`. Vector and hybrid candidates tie within noise, so `/ask` keeps hybrid (exact identifiers and code names are keyword-friendly, which this set under-represents).
- For answering, hit@3 / hit@5 matter more than hit@1, because the LLM reads the top 5. All modes score 0.85-0.89 on hit@5, so the model's answer quality, not the ordering, is the next thing to measure.
- Two PDF parser bugs found while reading these results: small-caps headings ("G OVERN") were split so a heading became the fragment "OVERN" (lines are now grouped by baseline and a capital plus following smaller capitals are merged), and figure/table captions ("Fig. 3 ...") replaced the real section heading (captions are no longer headings).
- Multi-passage and cross-document questions (n=5) are too few to read anything into; hit@1 is 0 by construction for them. They show that the top 5 usually comes from one document, which suggests a diversity step (limit chunks per document) if cross-document questions matter.
- Measured on a 2-core CPU the m3 reranker takes about 0.5 s per passage pair; on a GPU it should be far faster. Re-measure on the real machine before deciding the pool size.
