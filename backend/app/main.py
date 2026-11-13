"""
FastAPI entry point.

Run locally with:
    uv run uvicorn app.main:app --reload

If the frontend has been built (cd frontend && npm run build), this server also
serves it, so the whole app runs on one address. That's what we use for the
phone demo: one server, one HTTPS tunnel.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import usage
from app.config import BACKEND_DIR, settings
from app.routes import audio, documents, questions

# Show our own "odhu.*" log lines (Gnani/Gemini call timings) in the terminal.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


app = FastAPI(title="Odhu API", version="0.1.0")

# Let the React dev server (a different port) call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(questions.router)
app.include_router(audio.router)


@app.get("/api/health")
def health() -> dict:
    """Simple check that the server is up."""
    return {"status": "ok"}


@app.get("/api/usage")
def get_usage() -> dict:
    """How many Gnani and Gemini calls we've made, to keep an eye on credits and quota."""
    return usage.summary()


# Serve the built React app at "/". This must come after the API routes, so that
# /api/... is still handled by FastAPI. Skipped if the frontend hasn't been built.
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
