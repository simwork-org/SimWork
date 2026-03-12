from __future__ import annotations

from fastapi import APIRouter

from backend.models import (
    HypothesisRequest,
    QueryRequest,
    StartSessionRequest,
    SubmitSolutionRequest,
)
from backend.simulation_engine.dependencies import get_engine


router = APIRouter(prefix="/sessions")


@router.post("/start")
def start_session(request: StartSessionRequest):
    engine = get_engine()
    return engine.start_session(request.candidate_id, request.scenario_id)


@router.get("/{session_id}/scenario")
def get_scenario(session_id: str):
    engine = get_engine()
    return engine.get_scenario_details(session_id)


@router.post("/{session_id}/query")
def send_query(session_id: str, request: QueryRequest):
    engine = get_engine()
    return engine.handle_query(session_id, request.agent, request.query)


@router.post("/{session_id}/hypothesis")
def save_hypothesis(session_id: str, request: HypothesisRequest):
    engine = get_engine()
    return engine.save_hypothesis(session_id, request.hypothesis)


@router.get("/{session_id}/history")
def get_history(session_id: str):
    engine = get_engine()
    return engine.get_history(session_id)


@router.post("/{session_id}/submit")
def submit_solution(session_id: str, request: SubmitSolutionRequest):
    engine = get_engine()
    return engine.submit_solution(session_id, request)


@router.get("/{session_id}/status")
def get_status(session_id: str):
    engine = get_engine()
    return engine.get_status(session_id)
