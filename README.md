# Secure RAG Document Q&A

Single-user web app: upload documents, ask questions, get cited answers. Includes evals, cost tracking, caching, and prompt-injection defenses.

> See `docs/decisions.md` for trade-offs.

## Run everything with Docker

One command starts the database and the app (API + web UI) on http://localhost:8000:

```bash
cp .env.example .env               # optional: API keys and settings
docker compose up --build
```

- **LLM:** answers come from Ollama running on your computer (`ollama pull llama3.1:8b`), reached from the
  container at `host.docker.internal:11434`. With a Gemini, OpenAI or OpenRouter key in `.env`, that provider is used
  first and Ollama becomes the fallback.
- **First upload is slow:** the embedding and reranker models (about 3.5 GB) download once into the `models`
  volume. Later starts reuse them.
- **NVIDIA GPU:** the default image uses CPU PyTorch, so it runs anywhere. To use the GPU (Docker Desktop with WSL 2
  on Windows, or nvidia-container-toolkit on Linux):
  `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build`
- API docs: http://localhost:8000/api/docs. Eval result files are mounted read-only, so a new eval run shows on the
  Metrics page without a rebuild.
- Stop with `docker compose down`. Add `-v` to also delete the database and downloaded models.

How it fits together: a multi-stage `Dockerfile` builds the React app with Node, then copies the static files into
the Python image. `backend/app/web.py` serves the API under `/api` and the frontend at `/`, so the browser talks to a
single origin (no CORS) and strict security headers apply. Database migrations run on every start
(`docker/entrypoint.sh`); they do nothing when the schema is already current.

## Local development


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

Frontend (second terminal): `cd frontend && npm install && npm run dev` → http://localhost:5173 (see `frontend/README.md`).

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
frontend/           React + TypeScript UI (Vite, Tailwind)
backend/app/web.py  production entry: API under /api + built frontend at /
Dockerfile          frontend build + Python app in one image
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
