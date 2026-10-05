# One image for the whole app: the React build is served by FastAPI (backend/app/web.py).
# Build context is the repo root:   docker compose up --build

# ---- 1. Build the frontend -------------------------------------------------------------
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. Python app -----------------------------------------------------------------------
FROM python:3.12-slim

# PyTorch decides the image size. The default is the CPU build (about 1 GB less than CUDA and runs anywhere).
# docker-compose.gpu.yml switches this to the CUDA 12.8 build for NVIDIA GPUs (RTX 50-series needs cu128).
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models \
    FRONTEND_DIST=/app/static

WORKDIR /app

# torch first, from its own index, so sentence-transformers does not pull the much larger default build.
RUN pip install torch --index-url "$TORCH_INDEX"
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app
COPY backend/evals ./evals
COPY --from=frontend /frontend/dist ./static
COPY docker/entrypoint.sh /entrypoint.sh

# Run as an unprivileged user. /models (downloaded embedding models) is a volume.
# The sed strips Windows line endings, in case git converted the script on checkout.
RUN useradd --create-home --uid 10001 rag \
 && mkdir -p /models \
 && chown -R rag:rag /models \
 && sed -i 's/\r$//' /entrypoint.sh \
 && chmod +x /entrypoint.sh
USER rag

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.web:web", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
