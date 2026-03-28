"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
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
from fastapi.responses import JSONResponse  # noqa: E402

from api.routes import router  # noqa: E402
from investigation_logger.logger import init_db, close_pool, check_db  # noqa: E402

logger = logging.getLogger(__name__)

_LLM_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}


def _validate_env() -> None:
    """Log warnings for missing critical environment variables."""
    missing = []
    if not os.environ.get("DATABASE_URL"):
        missing.append("DATABASE_URL")
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        missing.append("GOOGLE_CLIENT_ID")
    provider = os.environ.get("LLM_PROVIDER", "ollama")
    key_name = _LLM_KEY_MAP.get(provider)
    if key_name and not os.environ.get(key_name):
        missing.append(key_name)
    if missing:
        logger.warning("Missing environment variables: %s", ", ".join(missing))


@asynccontextmanager
async def lifespan(_: FastAPI):
    _validate_env()
    init_db()
    logger.info("SimWork API started — database initialized")
    yield
    close_pool()
    logger.info("SimWork API shutting down — database pool closed")

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
    db_ok = check_db()
    status = "ok" if db_ok else "degraded"
    code = 200 if db_ok else 503
    return JSONResponse({"status": status, "database": db_ok}, status_code=code)
