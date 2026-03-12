"""FastAPI route definitions matching docs/6-api-spec.md."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from scenario_loader.loader import list_scenarios
from simulation_engine.engine import (
    get_scenario_details,
    get_session_status,
    handle_hypothesis,
    handle_query,
    handle_submission,
    start_session,
)
from investigation_logger.logger import get_query_history

router = APIRouter(prefix="/api/v1")


# ── Request / Response models ──────────────────────────────────────────


class StartSessionRequest(BaseModel):
    candidate_id: str
    scenario_id: str


class QueryRequest(BaseModel):
    agent: str
    query: str


class HypothesisRequest(BaseModel):
    hypothesis: str


class SubmitRequest(BaseModel):
    root_cause: str
    proposed_actions: list[str]
    summary: str


# ── Endpoints ──────────────────────────────────────────────────────────


@router.post("/sessions/start")
def api_start_session(req: StartSessionRequest):
    try:
        return start_session(req.candidate_id, req.scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "scenario_not_found", "message": f"Scenario '{req.scenario_id}' not found"})


@router.get("/sessions/{session_id}/scenario")
def api_get_scenario(session_id: str):
    try:
        return get_scenario_details(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(e)})


@router.post("/sessions/{session_id}/query")
def api_query_agent(session_id: str, req: QueryRequest):
    try:
        return handle_query(session_id, req.agent, req.query)
    except ValueError as e:
        msg = str(e)
        if "Invalid agent" in msg:
            raise HTTPException(status_code=400, detail={"error": "invalid_agent", "message": msg})
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": msg})


@router.post("/sessions/{session_id}/hypothesis")
def api_submit_hypothesis(session_id: str, req: HypothesisRequest):
    try:
        return handle_hypothesis(session_id, req.hypothesis)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(e)})


@router.get("/sessions/{session_id}/history")
def api_get_history(session_id: str):
    queries = get_query_history(session_id)
    return {"queries": queries}


@router.post("/sessions/{session_id}/submit")
def api_submit_solution(session_id: str, req: SubmitRequest):
    try:
        return handle_submission(session_id, req.root_cause, req.proposed_actions, req.summary)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(e)})


@router.get("/sessions/{session_id}/status")
def api_session_status(session_id: str):
    try:
        return get_session_status(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(e)})


@router.get("/scenarios")
def api_list_scenarios():
    return {"scenarios": list_scenarios()}
