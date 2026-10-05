"""Production entry point: the API under /api and the built React app at /, from one server.

In development the Vite dev server serves the frontend and forwards /api/* to `app.main:app`.
In Docker there is no Vite, so this wrapper does the same job:

    uvicorn app.web:web      ->  /api/...  the FastAPI app from app/main.py (docs at /api/docs)
                                 /...      files from the frontend build (FRONTEND_DIST)

Because the browser sees one origin either way, the API needs no CORS settings.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.main import app as api

FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))

# Sent with every response. The frontend loads nothing from other origins, so the policy can be strict:
# even if injected markup ever reached the page, it could not load scripts or send data elsewhere.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


class SPAStaticFiles(StaticFiles):
    """Static files, plus index.html for client-side routes such as /chat that have no file of their own."""

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Only page routes fall back. A missing /assets/app.js must stay a 404, not turn into HTML.
            if exc.status_code == 404 and "." not in Path(path).name:
                return await super().get_response("index.html", scope)
            raise


def _is_api_docs(path: str) -> bool:
    # Swagger UI at /api/docs loads its script and styles from a CDN, so it cannot run under the strict policy.
    return path.startswith(("/api/docs", "/api/redoc"))


def create_web(frontend_dist: Path = FRONTEND_DIST) -> FastAPI:
    web = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @web.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            if name == "Content-Security-Policy" and _is_api_docs(request.url.path):
                continue
            response.headers.setdefault(name, value)
        return response

    web.mount("/api", api)
    if (frontend_dist / "index.html").is_file():
        web.mount("/", SPAStaticFiles(directory=frontend_dist, html=True), name="frontend")
    return web


web = create_web()
