"""Scoring engine — deterministic process signals + LLM dimension scoring."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from investigation_logger.logger import (
    get_query_history,
    get_saved_evidence,
    get_scoring_result,
    get_session,
    get_session_events,
    get_submission,
    save_scoring_result,
)
from llm_interface.llm_client import LLMClient
from scenario_loader.loader import load_scenario

logger = logging.getLogger(__name__)

LEVEL_SCORES = {"excellent": 5, "good": 4, "adequate": 3, "poor": 2}
SCORE_LEVELS = {5: "excellent", 4: "good", 3: "adequate", 2: "poor", 1: "poor"}


def _compute_process_signals(
    session: dict[str, Any],
    queries: list[dict[str, Any]],
    events: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    submission: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """Compute deterministic process signals from logged data."""

    # Agent usage
    agents_used: dict[str, int] = {}
    for q in queries:
        agent = q["agent"]
        agents_used[agent] = agents_used.get(agent, 0) + 1

    # Input mode breakdown
    typed_count = 0
    suggestion_count = 0
    for ev in events:
        if ev["event_type"] == "query_submitted":
            mode = ev.get("event_payload", {}).get("input_mode", "typed")
            if mode == "suggestion":
                suggestion_count += 1
            else:
                typed_count += 1

    # Agent order (first query per agent)
    seen_agents: list[str] = []
    for q in queries:
        if q["agent"] not in seen_agents:
            seen_agents.append(q["agent"])

    # Evidence agent mix
    evidence_agents: dict[str, int] = {}
    for ev in evidence:
        agent = ev["agent"]
        evidence_agents[agent] = evidence_agents.get(agent, 0) + 1

    # Red herrings investigated
    red_herrings = scenario.get("red_herrings", [])
    red_herrings_investigated: list[str] = []
    all_query_text = " ".join(q.get("query", "").lower() for q in queries)
    all_query_text += " " + " ".join(q.get("response", "").lower() for q in queries)
    for rh in red_herrings:
        signal = rh.get("signal", "")
        keywords = _extract_keywords(signal)
        if any(kw in all_query_text for kw in keywords):
            red_herrings_investigated.append(signal)

    # Key findings alignment with saved evidence
    expected_findings = scenario.get("expected_key_findings", [])
    key_findings_saved: list[str] = []
    evidence_text = " ".join(
        (ev.get("annotation") or "") + " " + json.dumps(ev.get("artifact", {}))
        for ev in evidence
    ).lower()
    for finding in expected_findings:
        keywords = _extract_keywords(finding)
        matches = sum(1 for kw in keywords if kw in evidence_text)
        if matches >= min(2, len(keywords)):
            key_findings_saved.append(finding)

    # Session duration
    started_at = session.get("started_at", "")
    submission_ts = submission.get("timestamp", "")
    duration_minutes = 0.0
    if started_at and submission_ts:
        try:
            start = datetime.fromisoformat(started_at)
            end = datetime.fromisoformat(submission_ts)
            duration_minutes = round((end - start).total_seconds() / 60, 1)
        except (ValueError, TypeError):
            pass

    return {
        "agents_used": agents_used,
        "total_queries": len(queries),
        "evidence_saved_count": len(evidence),
        "evidence_agents": evidence_agents,
        "cross_agent_queries": len(agents_used) >= 2,
        "first_query_agents_order": seen_agents,
        "typed_vs_suggestion": {"typed": typed_count, "suggestion": suggestion_count},
        "red_herrings_investigated": red_herrings_investigated,
        "key_findings_saved": key_findings_saved,
        "session_duration_minutes": duration_minutes,
    }


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a finding or signal description."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to",
        "for", "of", "and", "or", "but", "not", "with", "from", "by", "as",
        "that", "this", "it", "its", "after", "before", "while", "do", "does",
        "did", "has", "have", "had", "be", "been", "being", "into", "most",
        "show", "shows", "remain", "remains", "other", "than", "also",
    }
    words = text.lower().split()
    return [w.strip(".,;:()\"'") for w in words if len(w) > 3 and w.lower().strip(".,;:()\"'") not in stop_words]


def _build_scoring_prompt(
    dimension: str,
    rubric: dict[str, Any],
    submission: dict[str, Any],
    evidence: list[dict[str, Any]],
    process_signals: dict[str, Any],
    queries: list[dict[str, Any]],
) -> tuple[str, str]:
    """Build system + user prompt for LLM scoring of a single dimension."""

    levels = rubric.get("levels", {})
    levels_text = "\n".join(f"- {level}: {desc}" for level, desc in levels.items())

    evidence_summary = ""
    for i, ev in enumerate(evidence, 1):
        artifact = ev.get("artifact", {})
        annotation = ev.get("annotation") or "No annotation"
        evidence_summary += f"{i}. [{ev.get('agent', '?')}] {artifact.get('title', 'Untitled')} — {annotation}\n"

    actions_text = ""
    for act in submission.get("proposed_actions", []):
        if isinstance(act, dict):
            actions_text += f"- [{act.get('priority', '?')}] {act.get('action', '')}\n"

    query_summary = ""
    for q in queries[-15:]:
        query_summary += f"- [{q['agent']}] {q['query']}\n"

    system = (
        "You are an expert evaluator for a product management hiring assessment. "
        "Score the candidate's performance on a single dimension using a 1-5 scale. "
        "Return ONLY a JSON object with keys: score (integer 1-5), level (excellent/good/adequate/poor), reasoning (2-3 sentences)."
    )

    user = f"""## Dimension: {dimension}
## Rubric levels:
{levels_text}

## Scoring scale:
5 = excellent, 4 = good, 3 = adequate, 2 = poor, 1 = very poor (worse than poor)

## Candidate's submission:
Root cause: {submission.get('root_cause', 'Not provided')}
Stakeholder summary: {submission.get('stakeholder_summary', 'Not provided')}

## Proposed actions:
{actions_text or 'None provided'}

## Saved evidence ({len(evidence)} items):
{evidence_summary or 'None saved'}

## Investigation queries (last 15):
{query_summary or 'None'}

## Process signals:
- Agents used: {json.dumps(process_signals.get('agents_used', {}))}
- Total queries: {process_signals.get('total_queries', 0)}
- Evidence saved: {process_signals.get('evidence_saved_count', 0)}
- Cross-agent investigation: {process_signals.get('cross_agent_queries', False)}
- Red herrings investigated: {json.dumps(process_signals.get('red_herrings_investigated', []))}
- Key findings saved: {len(process_signals.get('key_findings_saved', []))} of expected

Score this candidate on the "{dimension}" dimension. Return JSON only."""

    return system, user


def score_session(session_id: str) -> dict[str, Any]:
    """Score a completed session against the scenario rubric.

    Returns the full scoring result with dimension scores, process signals,
    highlights, missed signals, and red herrings engaged.
    """
    # Check for existing score
    existing = get_scoring_result(session_id)
    if existing:
        return existing

    session = get_session(session_id)
    if session is None:
        raise ValueError(f"Session not found: {session_id}")

    submission = get_submission(session_id)
    if submission is None:
        raise ValueError(f"No submission found for session: {session_id}")

    scenario = load_scenario(session["scenario_id"])
    queries = get_query_history(session_id)
    events = get_session_events(session_id)
    evidence = get_saved_evidence(session_id)

    # Part A: Deterministic process signals
    process_signals = _compute_process_signals(session, queries, events, evidence, submission, scenario)

    # Part B: LLM-scored dimensions
    rubric = scenario.get("evaluation_rubric", {})
    llm = LLMClient()
    llm.temperature = 0.3

    dimensions: dict[str, Any] = {}
    for dimension_key, dimension_rubric in rubric.items():
        weight = dimension_rubric.get("weight", 0.25)
        try:
            system, user = _build_scoring_prompt(
                dimension_key, dimension_rubric, submission, evidence, process_signals, queries
            )
            result = llm.chat(system, user)
            score = int(result.get("score", 3))
            score = max(1, min(5, score))
            level = result.get("level", SCORE_LEVELS.get(score, "adequate"))
            reasoning = result.get("reasoning", "")
        except Exception as exc:
            logger.warning(f"LLM scoring failed for {dimension_key}: {exc}")
            score = 3
            level = "adequate"
            reasoning = f"Scoring unavailable: {exc}"

        dimensions[dimension_key] = {
            "score": score,
            "weight": weight,
            "level": level,
            "reasoning": reasoning,
        }

    # Compute weighted overall score
    total_weight = sum(d["weight"] for d in dimensions.values())
    if total_weight > 0:
        overall_score = round(
            sum(d["score"] * d["weight"] for d in dimensions.values()) / total_weight, 1
        )
    else:
        overall_score = 3.0

    # Build highlights and missed signals
    highlights: list[str] = []
    missed_signals: list[str] = []
    expected_findings = scenario.get("expected_key_findings", [])
    saved_findings = set(process_signals.get("key_findings_saved", []))

    for finding in expected_findings:
        if finding in saved_findings:
            highlights.append(finding)
        else:
            missed_signals.append(finding)

    red_herrings_engaged = process_signals.get("red_herrings_investigated", [])

    highlights_blob = {
        "highlights": highlights,
        "missed_signals": missed_signals,
        "red_herrings_engaged": red_herrings_engaged,
    }

    # Persist
    save_scoring_result(session_id, overall_score, dimensions, process_signals, highlights_blob)

    return {
        "overall_score": overall_score,
        "dimensions": dimensions,
        "process_signals": process_signals,
        "highlights": highlights,
        "missed_signals": missed_signals,
        "red_herrings_engaged": red_herrings_engaged,
        "scored_at": submission["timestamp"],
    }
