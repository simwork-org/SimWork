"""FastAPI application entry point."""

from __future__ import annotations

import os

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
