"""FastAPI application entry point."""

from __future__ import annotations

import os
from pathlib import Path

# Load .env before any other imports that read env vars
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _, _val = _line.partition("=")
        os.environ.setdefault(_key.strip(), _val.strip())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from investigation_logger.logger import clear_all_session_data, init_db

app = FastAPI(
    title="SimWork API",
    description="Simulation platform for evaluating investigation and decision-making skills",
    version="0.1.0",
)

# CORS
origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def on_startup():
    init_db()
    clear_all_session_data()


@app.get("/health")
def health():
    return {"status": "ok"}
