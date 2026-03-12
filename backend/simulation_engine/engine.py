"""Simulation engine — orchestrates simulation sessions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from agent_router.router import route_query, validate_agent
from investigation_logger.logger import (
    create_session,
    get_queries_count,
    get_query_history,
    get_session,
    log_query,
    save_hypothesis,
    submit_solution,
)
from llm_interface.llm_client import LLMClient
from scenario_loader.loader import load_scenario

# Default time limit in minutes
DEFAULT_TIME_LIMIT = 30

# Lazy LLM client
_llm: LLMClient | None = None


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def start_session(candidate_id: str, scenario_id: str) -> dict[str, Any]:
    """Create a new simulation session."""
    scenario = load_scenario(scenario_id)
    session_id = f"session_{uuid.uuid4().hex[:12]}"

    create_session(session_id, candidate_id, scenario_id)

    return {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "problem_statement": scenario["problem_statement"],
        "available_agents": ["analyst", "ux_researcher", "developer"],
        "time_limit_minutes": DEFAULT_TIME_LIMIT,
    }


def get_scenario_details(session_id: str) -> dict[str, Any]:
    """Return scenario details for a session."""
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    scenario = load_scenario(session["scenario_id"])
    return {
        "scenario_id": scenario["scenario_id"],
        "title": scenario["title"],
        "problem_statement": scenario["problem_statement"],
    }


def handle_query(session_id: str, agent: str, query: str) -> dict[str, Any]:
    """Process a candidate query to an agent."""
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    if session["status"] != "active":
        raise ValueError("Session is no longer active")

    validate_agent(agent)

    # Get conversation history for context
    history = get_query_history(session_id)
    conversation_history = []
    for h in history[-6:]:  # last 6 exchanges for context
        conversation_history.append({"role": "user", "content": h["query"]})
        conversation_history.append({"role": "assistant", "content": h["response"]})

    result = route_query(
        llm=_get_llm(),
        scenario_id=session["scenario_id"],
        agent=agent,
        query=query,
        conversation_history=conversation_history if conversation_history else None,
    )

    log_query(session_id, agent, query, result["response"])
    return result


def handle_hypothesis(session_id: str, hypothesis: str) -> dict[str, Any]:
    """Save or update a hypothesis."""
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    version = save_hypothesis(session_id, hypothesis)
    return {"status": "saved", "hypothesis_version": version}


def handle_submission(
    session_id: str, root_cause: str, proposed_actions: list[str], summary: str
) -> dict[str, Any]:
    """Submit final solution."""
    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")
    submit_solution(session_id, root_cause, proposed_actions, summary)
    return {"status": "submitted", "session_complete": True}


def get_session_status(session_id: str) -> dict[str, Any]:
    """Return current session status."""
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
        "current_hypothesis": session["current_hypothesis"],
        "queries_made": get_queries_count(session_id),
    }
