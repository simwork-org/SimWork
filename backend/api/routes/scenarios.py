from __future__ import annotations

from fastapi import APIRouter

from backend.simulation_engine.dependencies import get_engine


router = APIRouter()


@router.get("/scenarios")
def list_scenarios() -> dict:
    engine = get_engine()
    return {"scenarios": [scenario.model_dump() for scenario in engine.list_scenarios()]}
