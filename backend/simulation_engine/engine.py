"""Simulation engine — orchestrates simulation sessions."""

from __future__ import annotations

import asyncio
import json as _json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable

from agent_router.router import route_query, validate_agent
from investigation_logger.logger import (
    create_session,
    get_queries_count,
    get_query_history,
    get_query_log_detail,
    get_saved_evidence,
    get_scoring_result,
    get_session,
    get_session_events,
    log_query,
    log_session_event,
    remove_evidence,
    save_evidence,
    submit_solution,
    update_evidence_annotation,
)
from llm_interface.llm_client import LLMClient
from scenario_loader.loader import get_agent_capability_profiles, load_reference, load_scenario
from scoring.scorer import score_session

DEFAULT_TIME_LIMIT = 30

UI_EVENT_TYPES = {
    "agent_selected",
    "suggestion_clicked",
    "reference_opened",
    "reference_tab_changed",
    "submission_started",
    "submission_evidence_selected",
}

_llm: LLMClient | None = None


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def start_session(candidate_id: str, scenario_id: str, challenge_id: str | None = None) -> dict[str, Any]:
    scenario = load_scenario(scenario_id)
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    create_session(session_id, candidate_id, scenario_id, challenge_id)

    problem_statement = scenario["problem_statement"]
    if challenge_id:
        problem = next((p for p in scenario.get("problems", []) if p["id"] == challenge_id), None)
        if problem and "challenge_problem_statement" in problem:
            problem_statement = problem["challenge_problem_statement"]

    return {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "challenge_id": challenge_id,
        "problem_statement": problem_statement,
        "available_agents": ["analyst", "ux_researcher", "engineering_lead"],
        "time_limit_minutes": DEFAULT_TIME_LIMIT,
    }


def get_challenges(scenario_id: str) -> dict[str, Any]:
    """Return candidate-safe challenge catalog for a scenario."""
    scenario = load_scenario(scenario_id)
    challenges = []
    for problem in scenario.get("problems", []):
        challenges.append({
            "id": problem["id"],
            "challenge_title": problem.get("challenge_title", problem["title"]),
            "challenge_prompt": problem.get("challenge_prompt", ""),
        })
    return {"scenario_id": scenario_id, "challenges": challenges}


def get_scenario_details(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    scenario = load_scenario(session["scenario_id"])
    reference = load_reference(session["scenario_id"])

    problem_statement = scenario["problem_statement"]
    challenge_id = session.get("challenge_id")
    if challenge_id:
        problem = next((p for p in scenario.get("problems", []) if p["id"] == challenge_id), None)
        if problem and "challenge_problem_statement" in problem:
            problem_statement = problem["challenge_problem_statement"]

    return {
        "scenario_id": scenario["scenario_id"],
        "title": scenario["title"],
        "challenge_id": challenge_id,
        "problem_statement": problem_statement,
        "reference_panel": reference,
        "agent_profiles": get_agent_capability_profiles(session["scenario_id"]),
    }


def handle_query(
    session_id: str,
    agent: str,
    query: str,
    input_mode: str = "typed",
    status_callback: Callable[[dict[str, str]], None] | None = None,
) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    if session["status"] != "active":
        raise ValueError("Session is no longer active")

    validate_agent(agent)
    history = get_query_history(session_id)
    result = route_query(
        llm=_get_llm(),
        scenario_id=session["scenario_id"],
        agent=agent,
        query=query,
        conversation_history=history[-20:] if history else None,
        status_callback=status_callback,
    )
    planner = result.pop("_planner", None)
    attempts = result.pop("_attempts", None)
    query_log_id = log_query(
        session_id,
        agent,
        query,
        result["response"],
        artifacts=result.get("artifacts"),
        citations=result.get("citations"),
        warnings=result.get("warnings"),
        planner=planner,
        attempts=attempts,
    )
    log_session_event(
        session_id,
        "query_submitted",
        {
            "agent": agent,
            "query_text": query,
            "input_mode": input_mode,
            "query_log_id": query_log_id,
        },
    )
    return {
        **result,
        "query_log_id": query_log_id,
    }


async def handle_query_stream(
    session_id: str,
    agent: str,
    query: str,
    input_mode: str = "typed",
) -> AsyncGenerator[str, None]:
    """SSE generator that yields status events during query processing."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def status_callback(event: dict[str, str]) -> None:
        queue.put_nowait(event)

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(
        None,
        lambda: handle_query(session_id, agent, query, input_mode, status_callback),
    )

    while True:
        # Drain any queued status events
        while not queue.empty():
            try:
                event = queue.get_nowait()
                yield f"data: {_json.dumps(event)}\n\n"
            except asyncio.QueueEmpty:
                break
        if future.done():
            # Drain remaining events
            while not queue.empty():
                try:
                    event = queue.get_nowait()
                    yield f"data: {_json.dumps(event)}\n\n"
                except asyncio.QueueEmpty:
                    break
            # Yield final result
            result = future.result()
            yield f"data: {_json.dumps({'stage': 'complete', 'result': result})}\n\n"
            break
        await asyncio.sleep(0.1)


def handle_log_event(session_id: str, event_type: str, event_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    if event_type not in UI_EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")
    event_id = log_session_event(session_id, event_type, event_payload or {})
    return {"status": "logged", "event_id": event_id}


def handle_get_saved_evidence(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    return {"evidence": get_saved_evidence(session_id)}


def handle_save_evidence(
    session_id: str,
    query_log_id: int,
    citation_id: str,
    agent: str,
    annotation: str | None = None,
) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    saved_id = save_evidence(session_id, query_log_id, citation_id, agent, annotation)
    evidence = get_saved_evidence(session_id)
    saved_item = next((item for item in evidence if item["id"] == saved_id), None)
    return {"status": "saved", "saved_evidence_id": saved_id, "evidence_count": len(evidence), "saved_evidence": saved_item}


def handle_remove_evidence(session_id: str, saved_evidence_id: int) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    removed = remove_evidence(session_id, saved_evidence_id)
    if not removed:
        raise ValueError(f"Saved evidence not found: {saved_evidence_id}")
    return {"status": "removed", "evidence_count": len(get_saved_evidence(session_id))}


def handle_update_evidence_annotation(session_id: str, saved_evidence_id: int, annotation: str | None) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    updated = update_evidence_annotation(session_id, saved_evidence_id, annotation)
    if not updated:
        raise ValueError(f"Saved evidence not found: {saved_evidence_id}")
    saved_item = next((item for item in get_saved_evidence(session_id) if item["id"] == saved_evidence_id), None)
    return {"status": "updated", "saved_evidence": saved_item}


def handle_submission(
    session_id: str,
    root_cause: str,
    supporting_evidence_ids: list[int],
    proposed_actions: list[dict[str, Any]],
    stakeholder_summary: str,
) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    submission_id = submit_solution(
        session_id,
        root_cause,
        supporting_evidence_ids,
        proposed_actions,
        stakeholder_summary,
    )
    log_session_event(
        session_id,
        "submission_completed",
        {
            "submission_id": submission_id,
            "supporting_evidence_ids": supporting_evidence_ids,
            "action_count": len(proposed_actions),
        },
    )
    return {"status": "submitted", "session_complete": True, "submission_id": submission_id}


def handle_get_query_log(session_id: str, query_log_id: int) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    detail = get_query_log_detail(session_id, query_log_id)
    if detail is None:
        raise ValueError(f"Query log not found: {query_log_id}")
    return detail


def get_session_status(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")

    started_at = datetime.fromisoformat(session["started_at"])
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds() / 60
    time_remaining = max(0, DEFAULT_TIME_LIMIT - elapsed)

    return {
        "session_id": session_id,
        "scenario_id": session["scenario_id"],
        "time_remaining_minutes": round(time_remaining, 1),
        "queries_made": get_queries_count(session_id),
        "saved_evidence_count": len(get_saved_evidence(session_id)),
    }


def get_session_process_log(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    return {"events": get_session_events(session_id)}


def handle_score_session(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    return score_session(session_id)


def handle_get_score(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    result = get_scoring_result(session_id)
    if result is None:
        raise ValueError(f"No scoring result for session: {session_id}")
    return result
