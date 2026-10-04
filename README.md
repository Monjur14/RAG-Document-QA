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
