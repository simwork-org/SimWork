"""FastAPI route definitions matching docs/6-api-spec.md."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import get_current_user, require_role
from investigation_logger.logger import (
    claim_invite_token,
    create_assessment,
    create_company,
    create_invite_token,
    get_assessment,
    get_assessment_candidates,
    get_assessments_by_company,
    get_company_by_owner,
    get_invite_token,
    get_invite_tokens_by_assessment,
    get_query_history,
    get_user,
    get_user_sessions,
    set_user_role,
)
from scenario_loader.loader import list_scenarios
from simulation_engine.engine import (
    get_challenges,
    get_scenario_details,
    get_session_process_log,
    get_session_status,
    handle_get_query_log,
    handle_get_saved_evidence,
    handle_get_score,
    handle_get_submission,
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


def _get_assigned_candidate_session(user_id: str) -> dict[str, Any] | None:
    sessions = get_user_sessions(user_id)
    return next((session for session in sessions if session.get("assessment_id") or session.get("invite_token")), None)


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
def api_start_session(req: StartSessionRequest, user: dict = Depends(get_current_user)):
    assigned_session = _get_assigned_candidate_session(user["user_id"])
    if assigned_session and assigned_session["scenario_id"] != req.scenario_id:
        raise HTTPException(
            status_code=403,
            detail="This account is restricted to the invited assessment scenario.",
        )
    try:
        return start_session(user["user_id"], req.scenario_id, req.challenge_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "scenario_not_found", "message": f"Scenario '{req.scenario_id}' not found"})


@router.get("/sessions/{session_id}/scenario")
def api_get_scenario(session_id: str, user: dict = Depends(get_current_user)):
    try:
        return get_scenario_details(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.post("/sessions/{session_id}/query")
def api_query_agent(session_id: str, req: QueryRequest, user: dict = Depends(get_current_user)):
    try:
        return handle_query(session_id, req.agent, req.query, input_mode=req.input_mode)
    except ValueError as exc:
        msg = str(exc)
        if "Invalid agent" in msg:
            raise HTTPException(status_code=400, detail={"error": "invalid_agent", "message": msg})
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": msg})


@router.post("/sessions/{session_id}/query/stream")
async def api_query_agent_stream(session_id: str, req: QueryRequest, user: dict = Depends(get_current_user)):
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
def api_log_session_event(session_id: str, req: SessionEventRequest, user: dict = Depends(get_current_user)):
    try:
        return handle_log_event(session_id, req.event_type, req.event_payload)
    except ValueError as exc:
        message = str(exc)
        status = 400 if "Unsupported event type" in message else 404
        error = "invalid_event" if status == 400 else "invalid_session"
        raise HTTPException(status_code=status, detail={"error": error, "message": message})


@router.get("/sessions/{session_id}/history")
def api_get_history(session_id: str, user: dict = Depends(get_current_user)):
    return {"queries": get_query_history(session_id)}


@router.get("/sessions/{session_id}/query/{query_log_id}")
def api_get_query_log(session_id: str, query_log_id: int, user: dict = Depends(get_current_user)):
    try:
        return handle_get_query_log(session_id, query_log_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})


@router.get("/sessions/{session_id}/evidence")
def api_get_saved_evidence(session_id: str, user: dict = Depends(get_current_user)):
    try:
        return handle_get_saved_evidence(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.post("/sessions/{session_id}/evidence")
def api_save_evidence(session_id: str, req: SaveEvidenceRequest, user: dict = Depends(get_current_user)):
    try:
        return handle_save_evidence(session_id, req.query_log_id, req.citation_id, req.agent, req.annotation)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.patch("/sessions/{session_id}/evidence/{saved_evidence_id}")
def api_update_saved_evidence(session_id: str, saved_evidence_id: int, req: UpdateEvidenceAnnotationRequest, user: dict = Depends(get_current_user)):
    try:
        return handle_update_evidence_annotation(session_id, saved_evidence_id, req.annotation)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_saved_evidence", "message": str(exc)})


@router.delete("/sessions/{session_id}/evidence/{saved_evidence_id}")
def api_delete_saved_evidence(session_id: str, saved_evidence_id: int, user: dict = Depends(get_current_user)):
    try:
        return handle_remove_evidence(session_id, saved_evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_saved_evidence", "message": str(exc)})


@router.post("/sessions/{session_id}/submit")
def api_submit_solution(session_id: str, req: SubmitRequest, user: dict = Depends(get_current_user)):
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
def api_session_status(session_id: str, user: dict = Depends(get_current_user)):
    try:
        return get_session_status(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.get("/sessions/{session_id}/events")
def api_session_events(session_id: str, user: dict = Depends(get_current_user)):
    try:
        return get_session_process_log(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "invalid_session", "message": str(exc)})


@router.post("/sessions/{session_id}/score")
def api_score_session(session_id: str, user: dict = Depends(get_current_user)):
    try:
        return handle_score_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "scoring_error", "message": str(exc)})


@router.get("/sessions/{session_id}/score")
def api_get_score(session_id: str, user: dict = Depends(get_current_user)):
    try:
        return handle_get_score(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "score_not_found", "message": str(exc)})


@router.get("/sessions/{session_id}/submission")
def api_get_submission(session_id: str, user: dict = Depends(get_current_user)):
    try:
        return handle_get_submission(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "submission_not_found", "message": str(exc)})


@router.get("/me")
def api_get_me(user: dict = Depends(get_current_user)):
    profile = get_user(user["user_id"])
    if profile is None:
        result = dict(user)
    else:
        result = dict(profile)
    # Include company_id if user is a company owner
    if result.get("role") == "company":
        company = get_company_by_owner(user["user_id"])
        result["company_id"] = company["id"] if company else None
    return result


class SetRoleRequest(BaseModel):
    role: Literal["company", "candidate"]


@router.post("/me/role")
def api_set_role(req: SetRoleRequest, user: dict = Depends(get_current_user)):
    """Set the role for a user."""
    existing = get_user(user["user_id"])
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    set_user_role(user["user_id"], req.role)
    return {"role": req.role}


@router.get("/me/sessions")
def api_get_my_sessions(user: dict = Depends(get_current_user)):
    return {"sessions": get_user_sessions(user["user_id"])}


@router.get("/scenarios")
def api_list_scenarios(user: dict = Depends(get_current_user)):
    scenarios = list_scenarios()
    assigned_session = _get_assigned_candidate_session(user["user_id"])
    if assigned_session:
        scenarios = [scenario for scenario in scenarios if scenario["id"] == assigned_session["scenario_id"]]
    return {"scenarios": scenarios}


@router.get("/scenarios/{scenario_id}/challenges")
def api_get_challenges(scenario_id: str, user: dict = Depends(get_current_user)):
    assigned_session = _get_assigned_candidate_session(user["user_id"])
    if assigned_session and assigned_session["scenario_id"] != scenario_id:
        raise HTTPException(
            status_code=403,
            detail="This account is restricted to the invited assessment scenario.",
        )
    try:
        return get_challenges(scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "scenario_not_found", "message": f"Scenario '{scenario_id}' not found"})


# ── Company endpoints ──


class CreateCompanyRequest(BaseModel):
    name: str


@router.post("/companies")
def api_create_company(req: CreateCompanyRequest, user: dict = Depends(require_role("company"))):
    existing = get_company_by_owner(user["user_id"])
    if existing:
        return existing
    company_id = create_company(req.name, user["user_id"])
    return {"id": company_id, "name": req.name, "owner_user_id": user["user_id"]}


@router.get("/companies/me")
def api_get_my_company(user: dict = Depends(require_role("company"))):
    company = get_company_by_owner(user["user_id"])
    if not company:
        raise HTTPException(status_code=404, detail="Company profile not found. Create one first.")
    return company


# ── Assessment endpoints ──


class CreateAssessmentRequest(BaseModel):
    scenario_id: str
    challenge_id: Optional[str] = None
    title: Optional[str] = None


@router.post("/assessments")
def api_create_assessment(req: CreateAssessmentRequest, user: dict = Depends(require_role("company"))):
    company = get_company_by_owner(user["user_id"])
    if not company:
        raise HTTPException(status_code=400, detail="Create a company profile first.")
    import uuid
    assessment_id = uuid.uuid4().hex[:12]
    create_assessment(assessment_id, company["id"], req.scenario_id, req.challenge_id, req.title)
    return {"id": assessment_id, "scenario_id": req.scenario_id, "challenge_id": req.challenge_id, "title": req.title}


@router.get("/assessments")
def api_list_assessments(user: dict = Depends(require_role("company"))):
    company = get_company_by_owner(user["user_id"])
    if not company:
        return {"assessments": []}
    return {"assessments": get_assessments_by_company(company["id"])}


@router.get("/assessments/{assessment_id}")
def api_get_assessment(assessment_id: str, user: dict = Depends(require_role("company"))):
    company = get_company_by_owner(user["user_id"])
    assessment = get_assessment(assessment_id)
    if not assessment or (company and assessment["company_id"] != company["id"]):
        raise HTTPException(status_code=404, detail="Assessment not found")
    candidates = get_assessment_candidates(assessment_id)
    invites = get_invite_tokens_by_assessment(assessment_id)
    return {"assessment": assessment, "candidates": candidates, "invites": invites}


# ── Invite endpoints ──


class GenerateInviteRequest(BaseModel):
    candidate_email: Optional[str] = None


@router.post("/assessments/{assessment_id}/invite")
def api_generate_invite(assessment_id: str, req: GenerateInviteRequest, user: dict = Depends(require_role("company"))):
    company = get_company_by_owner(user["user_id"])
    assessment = get_assessment(assessment_id)
    if not assessment or (company and assessment["company_id"] != company["id"]):
        raise HTTPException(status_code=404, detail="Assessment not found")
    import uuid
    token = uuid.uuid4().hex[:12]
    create_invite_token(token, assessment_id, req.candidate_email)
    return {"token": token, "invite_url": f"/invite/{token}"}


@router.get("/invite/{token}")
def api_validate_invite(token: str):
    """Public endpoint — no auth required. Returns assessment info for the invite landing page."""
    invite = get_invite_token(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite link")
    if invite.get("used_at"):
        raise HTTPException(status_code=410, detail="This invite has already been used")
    return {
        "token": token,
        "scenario_id": invite["scenario_id"],
        "assessment_title": invite.get("assessment_title"),
        "company_name": invite.get("company_name"),
    }


class ClaimInviteRequest(BaseModel):
    pass


@router.post("/invite/{token}/claim")
def api_claim_invite(token: str, user: dict = Depends(get_current_user)):
    invite = get_invite_token(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite link")
    if invite.get("used_at"):
        raise HTTPException(status_code=410, detail="This invite has already been used")
    if invite.get("candidate_email") and invite["candidate_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="This invite was sent to a different email address")

    # Ensure user role is candidate
    set_user_role(user["user_id"], "candidate")

    # Claim the token
    claim_invite_token(token, user["user_id"])

    # Start a session for the candidate
    session_data = start_session(
        user["user_id"],
        invite["scenario_id"],
        invite.get("challenge_id"),
        assessment_id=invite["assessment_id"],
        invite_token=token,
    )
    return {
        "session_id": session_data["session_id"],
        "claimed": True,
        "company_name": invite.get("company_name"),
        "assessment_title": invite.get("assessment_title"),
    }
