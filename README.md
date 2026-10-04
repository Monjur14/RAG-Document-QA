# Secure RAG Document Q&A

Single-user web app: upload documents, ask questions, get cited answers. Includes evals, cost tracking, caching, and prompt-injection defenses.

> Status: Week 0/1 foundation (upload + parsing). See `docs/decisions.md` for trade-offs.

## Quick start

```bash
cp .env.example .env
docker compose up -d db          # PostgreSQL + pgvector

cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
# PyTorch with GPU support first (RTX 50-series needs the CUDA 12.8 build):
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
python -m app.db                 # create/upgrade the database (runs migrations)
pytest                           # run tests
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

Smoke-test the real embedding model (downloads ~1.3 GB the first time): `python -m app.embeddings`

## Try it

```bash
curl -F "file=@README.md" http://localhost:8000/documents/upload
```

## Search and evals

```bash
curl -X POST localhost:8000/search -H "Content-Type: application/json" \
  -d '{"query": "how do I reset my password", "k": 5, "mode": "hybrid"}'   # mode: vector | keyword | hybrid

python -m evals.retrieval_eval    # seed eval: hit@k and MRR per mode; saves JSON to backend/evals/results/
```

## Ask questions

Needs Ollama running with a model pulled (`ollama pull llama3.1:8b`). Settings come from `.env` (see `.env.example`).

```bash
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "How do I install Orbit?"}'
# -> answer with [n] citations, plus status: answered | insufficient_evidence | model_declined | uncited

python -m evals.threshold_eval    # calibrate the "I don't know" threshold (MIN_VECTOR_SCORE)
```

## Layout

```
backend/app/        FastAPI app (thin API layer)
backend/app/parsers one parser per format (txt, md, html, pdf, docx) -> normalized ParsedSection
backend/tests/      unit + API tests
frontend/           React/Next.js UI (later)
docs/decisions.md   decision log
```

## Database migrations

The schema is managed with Alembic (plain SQL migrations in `backend/migrations/versions/`). Run from `backend/`:

```bash
alembic upgrade head              # create or update the database to the latest schema
alembic downgrade base            # drop everything (destroys data)
alembic current                   # show the current version
alembic revision -m "add xyz"     # new empty migration; fill in upgrade() and downgrade()
```

Never edit an already-committed migration; add a new one.
