"""
api/main.py — FastAPI application entry point.
Run: uvicorn api.main:app --reload --port 8000
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path so all existing modules resolve correctly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize DB on startup
from repositories.database import init_db
from config.settings import get_settings
from utils.logging_config import setup_logging

setup_logging()
settings = get_settings()
settings.ensure_directories()
init_db()

from api.routers import course, questions, papers, audit, settings as settings_router
from api.routers.course import subjects_router

app = FastAPI(
    title="Prashnopatra API",
    description="AI-powered question paper generation system for Generative AI course",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS — allow Next.js dev server ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(course.router,           prefix="/api")
app.include_router(subjects_router,         prefix="/api")
app.include_router(questions.router,        prefix="/api")
app.include_router(papers.router,           prefix="/api")
app.include_router(audit.router,            prefix="/api")
app.include_router(settings_router.router,  prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0", "app": "Prashnopatra"}
