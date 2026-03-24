"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
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

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.routes import router  # noqa: E402
from investigation_logger.logger import init_db  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="SimWork API",
    description="Simulation platform for evaluating investigation and decision-making skills",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
default_origins = "http://localhost:3000,http://127.0.0.1:3000"
origins = os.environ.get("CORS_ORIGINS", default_origins).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
