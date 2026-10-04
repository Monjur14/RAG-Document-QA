# Secure RAG Document Q&A

Single-user web app: upload documents, ask questions, get cited answers. Includes evals, cost tracking, caching, and prompt-injection defenses.

> Status: Week 0/1 foundation (upload + parsing). See `docs/decisions.md` for trade-offs.

## Quick start

```bash
cp .env.example .env
docker compose up -d db          # PostgreSQL + pgvector

cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.db                 # create/upgrade the database (runs migrations)
pytest                           # run tests
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

## Try it

```bash
curl -F "file=@README.md" http://localhost:8000/documents/upload
```

## Layout

```
backend/app/        FastAPI app (thin API layer)
backend/app/parsers one parser per format -> normalized ParsedSection
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
