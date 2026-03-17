"""FastAPI route definitions matching docs/6-api-spec.md."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from investigation_logger.logger import get_query_history
from scenario_loader.loader import list_scenarios
from simulation_engine.engine import (
    get_challenges,
    get_scenario_details,
    get_session_process_log,
    get_session_status,
    handle_get_query_log,
    handle_get_saved_evidence,
    handle_get_score,
    handle_log_event,
    handle_query,
    handle_query_stream,
    handle_remove_evidence,
    handle_save_evidence,
    handle_score_session,
    handle_submission,
    handle_update_evidence_annotation,
    start_session,
)

router = APIRouter(prefix="/api/v1")


class StartSessionRequest(BaseModel):
    candidate_id: str
    scenario_id: str
    challenge_id: Optional[str] = None


class QueryRequest(BaseModel):
    agent: str
    query: str
    input_mode: Literal["typed", "suggestion"] = "typed"


class SessionEventRequest(BaseModel):
    event_type: str
    event_payload: dict[str, Any] = Field(default_factory=dict)


class SaveEvidenceRequest(BaseModel):
    query_log_id: int
    citation_id: str
    agent: str
    annotation: Optional[str] = None


class UpdateEvidenceAnnotationRequest(BaseModel):
    annotation: Optional[str] = None


class ProposedActionRequest(BaseModel):
    action: str
    priority: Literal["P0", "P1", "P2"]


class SubmitRequest(BaseModel):
    root_cause: str
    supporting_evidence_ids: list[int]
    proposed_actions: list[ProposedActionRequest]
    stakeholder_summary: str


@router.post("/sessions/start")
def api_start_session(req: StartSessionRequest):
    try:
        return start_session(req.candidate_id, req.scenario_id, req.challenge_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "scenario_not_found", "message": f"Scenario '{req.scenario_id}' not found"})


@router.get("/sessions/{session_id}/scenario")
def api_get_scenario(session_id: str):
    try:
        return get_scenario_details(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.post("/sessions/{session_id}/query")
def api_query_agent(session_id: str, req: QueryRequest):
    try:
        return handle_query(session_id, req.agent, req.query, input_mode=req.input_mode)
    except ValueError as exc:
        msg = str(exc)
        if "Invalid agent" in msg:
            raise HTTPException(status_code=400, detail={"error": "invalid_agent", "message": msg})
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": msg})


@router.post("/sessions/{session_id}/query/stream")
async def api_query_agent_stream(session_id: str, req: QueryRequest):
    try:
        return StreamingResponse(
            handle_query_stream(session_id, req.agent, req.query, input_mode=req.input_mode),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except ValueError as exc:
        msg = str(exc)
        if "Invalid agent" in msg:
            raise HTTPException(status_code=400, detail={"error": "invalid_agent", "message": msg})
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": msg})


@router.post("/sessions/{session_id}/events")
def api_log_session_event(session_id: str, req: SessionEventRequest):
    try:
        return handle_log_event(session_id, req.event_type, req.event_payload)
    except ValueError as exc:
        message = str(exc)
        status = 400 if "Unsupported event type" in message else 404
        error = "invalid_event" if status == 400 else "invalid_session"
        raise HTTPException(status_code=status, detail={"error": error, "message": message})


@router.get("/sessions/{session_id}/history")
def api_get_history(session_id: str):
    return {"queries": get_query_history(session_id)}


@router.get("/sessions/{session_id}/query/{query_log_id}")
def api_get_query_log(session_id: str, query_log_id: int):
    try:
        return handle_get_query_log(session_id, query_log_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})


@router.get("/sessions/{session_id}/evidence")
def api_get_saved_evidence(session_id: str):
    try:
        return handle_get_saved_evidence(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.post("/sessions/{session_id}/evidence")
def api_save_evidence(session_id: str, req: SaveEvidenceRequest):
    try:
        return handle_save_evidence(session_id, req.query_log_id, req.citation_id, req.agent, req.annotation)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.patch("/sessions/{session_id}/evidence/{saved_evidence_id}")
def api_update_saved_evidence(session_id: str, saved_evidence_id: int, req: UpdateEvidenceAnnotationRequest):
    try:
        return handle_update_evidence_annotation(session_id, saved_evidence_id, req.annotation)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_saved_evidence", "message": str(exc)})


@router.delete("/sessions/{session_id}/evidence/{saved_evidence_id}")
def api_delete_saved_evidence(session_id: str, saved_evidence_id: int):
    try:
        return handle_remove_evidence(session_id, saved_evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_saved_evidence", "message": str(exc)})


@router.post("/sessions/{session_id}/submit")
def api_submit_solution(session_id: str, req: SubmitRequest):
    try:
        return handle_submission(
            session_id,
            req.root_cause,
            req.supporting_evidence_ids,
            [action.model_dump() for action in req.proposed_actions],
            req.stakeholder_summary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.get("/sessions/{session_id}/status")
def api_session_status(session_id: str):
    try:
        return get_session_status(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.get("/sessions/{session_id}/events")
def api_session_events(session_id: str):
    try:
        return get_session_process_log(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.post("/sessions/{session_id}/score")
def api_score_session(session_id: str):
    try:
        return handle_score_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "scoring_error", "message": str(exc)})


@router.get("/sessions/{session_id}/score")
def api_get_score(session_id: str):
    try:
        return handle_get_score(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "score_not_found", "message": str(exc)})


@router.get("/scenarios")
def api_list_scenarios():
    return {"scenarios": list_scenarios()}


@router.get("/scenarios/{scenario_id}/challenges")
def api_get_challenges(scenario_id: str):
    try:
        return get_challenges(scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "scenario_not_found", "message": f"Scenario '{scenario_id}' not found"})
