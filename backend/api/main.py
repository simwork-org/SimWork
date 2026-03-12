from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.scenarios import router as scenarios_router
from backend.api.routes.sessions import router as sessions_router
from backend.config import get_settings


settings = get_settings()

app = FastAPI(
    title="SimWork API",
    description="Simulation interview backend for domain-restricted AI teammate workflows",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(scenarios_router, prefix=settings.api_prefix)
app.include_router(sessions_router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
