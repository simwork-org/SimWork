"""Agent router — evidence-first planning, execution, and synthesis."""

from __future__ import annotations

import json
import logging
from typing import Any

from agent_router.evidence import execute_operations, get_agent_source_metadata, summarize_evidence
from llm_interface.llm_client import LLMClient
from scenario_loader.loader import get_agent_capability_profile
from telemetry_layer.telemetry import VALID_AGENTS

logger = logging.getLogger(__name__)

AGENT_PERSONAS: dict[str, str] = {
    "analyst": (
        "You are Priya, Senior Data Analyst at ZaikaNow. You focus on business metrics, trends, funnels, "
        "segments, orders, and payments. You do not speculate about UX or engineering causes outside your evidence."
    ),
    "ux_researcher": (
        "You are Kavya, UX Researcher at ZaikaNow. You focus on qualitative feedback, usability, support tickets, "
        "and UX changes. You do not speculate about engineering metrics or analytics outside your evidence."
    ),
    "engineering_lead": (
        "You are Rohan, Engineering Lead at ZaikaNow. You focus on deployments, service health, architecture, "
        "and payment errors. You do not speculate about product analytics or qualitative feedback outside your evidence."
    ),
}

PLANNER_RESPONSE_SCHEMA = {
    "intent": "lookup | compare | trend | funnel | explain | summarize",
    "intent_class": "reference | dataset_summary | schema_question | investigation | comparison | trend_analysis | root_cause_analysis | quote_lookup | incident_timeline",
    "answer_mode": "metric | chart | table | text",
    "operations": [
        {
            "alias": "short_name_for_reuse",
            "type": "lookup_rows | rank_rows | aggregate_breakdown | aggregate_timeseries | compute_funnel | read_document_excerpt | summarize_source_profile | summarize_date_span | compare_segments | summarize_metric_delta | extract_feedback_themes | select_representative_quotes | count_issue_mentions | summarize_ux_change_impact | build_incident_timeline | correlate_deployments_with_metrics | summarize_error_shift | compare_pre_post_rollout",
            "source": "allowed source filename",
            "title": "artifact title",
        }
    ],
    "needs_clarification": None,
    "pending_follow_up": {
        "prompt": "Short follow-up question for the user",
        "choices": ["Concrete follow-up choice"],
        "default_choice": "Default choice used when the user says yes",
        "resolved_query_template": "{choice}",
    },
    "next_steps": ["follow-up prompt"],
}

DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "analyst": {
        "orders", "revenue", "trend", "trends", "funnel", "conversion", "segment", "segments",
        "platform", "os", "payment", "payments", "users", "customer", "cohort", "daily", "weekly",
    },
    "ux_researcher": {
        "review", "reviews", "ticket", "tickets", "feedback", "usability", "research", "sentiment",
        "complaint", "complaints", "ux", "users saying",
    },
    "engineering_lead": {
        "deployment", "deployments", "latency", "error", "errors", "service", "services", "incident",
        "architecture", "timeout", "gateway", "p95", "p99", "rollback",
    },
}

DOMAIN_REDIRECTS = {
    "analyst": "That question belongs with Priya, the Data Analyst.",
    "ux_researcher": "That question belongs with Kavya, the UX Researcher.",
    "engineering_lead": "That question belongs with Rohan, the Engineering Lead.",
}


def validate_agent(agent: str) -> None:
    if agent not in VALID_AGENTS:
        raise ValueError(f"Invalid agent: {agent}. Valid agents: {sorted(VALID_AGENTS)}")


def route_query(
    llm: LLMClient,
    scenario_id: str,
    agent: str,
    query: str,
    conversation_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Route a candidate query through planner, deterministic execution, and synthesis."""
    validate_agent(agent)
    history = conversation_history or []
    follow_up_resolution = _resolve_follow_up_query(agent, query, history)

    if follow_up_resolution.get("handled_response"):
        pending_follow_up = follow_up_resolution.get("pending_follow_up")
        return {
            "agent": agent,
            "response": follow_up_resolution["handled_response"],
            "artifacts": [],
            "citations": [],
            "warnings": [follow_up_resolution["note"]] if follow_up_resolution.get("note") else [],
            "next_steps": pending_follow_up.get("choices", []) if pending_follow_up else [],
            "pending_follow_up": pending_follow_up,
            "intent_class": "reference",
            "_planner": {
                "original_query": query,
                "effective_query": query,
                "pending_follow_up": pending_follow_up,
                "next_steps": pending_follow_up.get("choices", []) if pending_follow_up else [],
            },
        }

    effective_query = follow_up_resolution["effective_query"]

    redirect = _domain_redirect(agent, effective_query)
    if redirect:
        return {
            "agent": agent,
            "response": redirect,
            "artifacts": [],
            "citations": [],
            "warnings": [redirect],
            "next_steps": [],
            "pending_follow_up": None,
            "intent_class": "reference",
        }

    source_metadata = get_agent_source_metadata(scenario_id, agent)
    capability_profile = get_agent_capability_profile(scenario_id, agent)
    prior_summaries = summarize_evidence(history, agent)
    last_turn_context = _last_agent_turn_context(history, agent)

    planner, planner_warning = _plan_query(
        llm,
        scenario_id,
        agent,
        effective_query,
        source_metadata,
        capability_profile,
        prior_summaries,
        last_turn_context,
    )
    planner = _apply_deterministic_intent_plan(agent, effective_query, planner, source_metadata)
    intent_class = _resolve_intent_class(agent, effective_query, planner, source_metadata)
    execution = execute_operations(
        scenario_id=scenario_id,
        agent=agent,
        operations=planner.get("operations", []),
        query_text=effective_query,
        answer_mode=planner.get("answer_mode", "table"),
        intent_class=intent_class,
        capability_profile=capability_profile,
    )

    warnings = execution["warnings"][:]
    if planner_warning:
        warnings.append(planner_warning)
    if follow_up_resolution.get("note"):
        warnings.append(follow_up_resolution["note"])
    if planner.get("needs_clarification"):
        warnings.append(str(planner["needs_clarification"]))

    pending_follow_up = _resolve_pending_follow_up(planner, effective_query, execution["artifacts"])
    next_steps = planner.get("next_steps") or _default_next_steps(agent, effective_query)
    response = _synthesize_response(
        llm=llm,
        agent=agent,
        query=effective_query,
        planner=planner,
        intent_class=intent_class,
        citations=execution["citations"],
        warnings=warnings,
        artifacts=execution["artifacts"],
        evidence=execution["evidence"],
        next_steps=next_steps,
        pending_follow_up=pending_follow_up,
    )

    planner_context = {
        **planner,
        "intent_class": intent_class,
        "next_steps": next_steps,
        "original_query": query,
        "effective_query": effective_query,
        "pending_follow_up": pending_follow_up,
    }

    return {
        "agent": agent,
        "response": response,
        "artifacts": execution["artifacts"],
        "citations": execution["citations"],
        "warnings": warnings,
        "next_steps": next_steps,
        "pending_follow_up": pending_follow_up,
        "intent_class": intent_class,
        "_planner": planner_context,
    }


def _plan_query(
    llm: LLMClient,
    scenario_id: str,
    agent: str,
    query: str,
    source_metadata: list[dict[str, Any]],
    capability_profile: dict[str, Any],
    prior_summaries: list[str],
    last_turn_context: dict[str, Any] | None,
) -> tuple[dict[str, Any], str | None]:
    system = (
        f"{AGENT_PERSONAS[agent]}\n\n"
        "Plan the minimum set of deterministic data operations needed to answer the current question. "
        "Do not answer the user. Return JSON only.\n\n"
        "Rules:\n"
        "- Use only the listed sources.\n"
        "- Stay within the agent's supported intents and operations.\n"
        "- Prefer 1-3 operations.\n"
        "- If later operations depend on earlier rows, give the earlier op an alias and refer to values as $alias.rows.0.column.\n"
        "- If the question is ambiguous, set needs_clarification to a short explanation but still provide the safest plan you can.\n"
        "- answer_mode must be one of metric, chart, table, text.\n"
        "- For singular requests like first/top/latest, use sort_by + limit 1 so tie detection can run.\n"
        "- For document questions, use read_document_excerpt.\n"
        "- For dataset summaries, schema questions, or date-range questions, prefer summarize_source_profile or summarize_date_span.\n"
        "- For UX themes or quotes, prefer extract_feedback_themes, count_issue_mentions, or select_representative_quotes.\n"
        "- For engineering timelines or rollout analysis, prefer build_incident_timeline, summarize_error_shift, or compare_pre_post_rollout.\n"
        f"Return exactly this JSON shape: {json.dumps(PLANNER_RESPONSE_SCHEMA)}"
    )
    user = json.dumps(
        {
            "scenario_id": scenario_id,
            "question": query,
            "capability_profile": capability_profile,
            "sources": source_metadata,
            "recent_evidence_summaries": prior_summaries,
            "last_agent_turn": last_turn_context,
        },
        ensure_ascii=True,
    )

    try:
        planner = llm.chat(system=system, user=user)
        if not isinstance(planner, dict):
            raise ValueError("Planner did not return a JSON object")
        planner.setdefault("intent", "summarize")
        planner.setdefault("intent_class", _resolve_intent_class(agent, query, planner, source_metadata))
        planner.setdefault("answer_mode", "table")
        planner.setdefault("operations", [])
        planner.setdefault("next_steps", [])
        planner.setdefault("needs_clarification", None)
        planner["pending_follow_up"] = _normalize_pending_follow_up(planner.get("pending_follow_up"))
        return planner, None
    except Exception as exc:
        logger.warning("Planner failed, using deterministic fallback: %s", exc)
        return _fallback_plan(query, source_metadata), "Planner fallback used due to invalid planner output."


def _fallback_plan(query: str, source_metadata: list[dict[str, Any]]) -> dict[str, Any]:
    q = query.lower()
    source_names = [item["name"] for item in source_metadata]

    if any(token in q for token in ("each dataset", "each table", "all datasets", "all tables", "dataset summary", "summarize the datasets")):
        return {
            "intent": "summarize",
            "intent_class": "dataset_summary",
            "answer_mode": "text",
            "operations": [
                {
                    "type": "summarize_source_profile",
                    "source": source_name,
                    "title": f"{source_name} profile",
                }
                for source_name in source_names[:6]
            ],
            "needs_clarification": None,
            "pending_follow_up": None,
            "next_steps": [],
        }

    if any(token in q for token in ("date range", "duration", "how long", "span", "coverage")):
        explicit_source = next((name for name in source_names if name in q), None)
        target_source = explicit_source or (source_names[0] if source_names else "")
        return {
            "intent": "summarize",
            "intent_class": "schema_question",
            "answer_mode": "text",
            "operations": [{
                "type": "summarize_date_span",
                "source": target_source,
                "title": f"{target_source} date coverage",
            }],
            "needs_clarification": None,
            "pending_follow_up": None,
            "next_steps": [],
        }

    if "funnel" in q and "sessions_events.csv" in source_names:
        return {
            "intent": "funnel",
            "intent_class": "investigation",
            "answer_mode": "chart",
            "operations": [{
                "type": "compute_funnel",
                "source": "sessions_events.csv",
                "title": "Checkout funnel",
            }],
            "needs_clarification": None,
            "pending_follow_up": {
                "prompt": "Would you like to break down the funnel by platform or app version?",
                "choices": [
                    "Break down the funnel by platform.",
                    "Break down the funnel by app version.",
                ],
                "default_choice": "Break down the funnel by platform.",
                "resolved_query_template": "{choice}",
            },
            "next_steps": [
                "Break down the funnel by platform.",
                "Break down the funnel by app version.",
            ],
        }

    if any(token in q for token in ("trend", "daily", "weekly", "monthly", "over time")):
        source = "orders.csv" if "orders.csv" in source_names else source_names[0]
        granularity = "month" if "month" in q else "day"
        return {
            "intent": "trend",
            "intent_class": "trend_analysis",
            "answer_mode": "chart",
            "operations": [{
                "type": "aggregate_timeseries",
                "source": source,
                "metric": "order_id" if source == "orders.csv" else None,
                "agg": "count",
                "granularity": granularity,
                "group_by": "platform" if any(token in q for token in ("platform", "os")) and source == "orders.csv" else None,
                "title": "Trend analysis",
            }],
            "needs_clarification": None,
            "pending_follow_up": {
                "prompt": "Would you like to break down the trend further?",
                "choices": [
                    "Break down the previous trend by platform.",
                    "Break down the previous trend by order status.",
                    "Show the previous trend aggregated monthly.",
                ],
                "default_choice": "Break down the previous trend by platform.",
                "resolved_query_template": "{choice}",
            },
            "next_steps": [
                "Break down the previous trend by platform.",
                "Break down the previous trend by order status.",
                "Show the previous trend aggregated monthly.",
            ],
        }

    if any(token in q for token in ("split", "break down", "by platform", "by os")):
        source = "orders.csv" if "orders.csv" in source_names else source_names[0]
        columns = _source_columns(source_metadata, source)
        return {
            "intent": "compare",
            "intent_class": "comparison",
            "answer_mode": "chart",
            "operations": [{
                "type": "aggregate_breakdown",
                "source": source,
                "group_by": "platform" if "platform" in columns else (columns[0] if columns else "platform"),
                "metric": "order_id" if source == "orders.csv" else None,
                "agg": "count",
                "title": "Breakdown",
            }],
            "needs_clarification": None,
            "pending_follow_up": {
                "prompt": "Would you like to continue the breakdown?",
                "choices": [
                    "Show the same breakdown over time.",
                    "Rank the strongest and weakest segments in the previous breakdown.",
                ],
                "default_choice": "Show the same breakdown over time.",
                "resolved_query_template": "{choice}",
            },
            "next_steps": [
                "Show the same breakdown over time.",
                "Rank the strongest and weakest segments in the previous breakdown.",
            ],
        }

    if "first customer" in q and "users.csv" in source_names:
        return {
            "intent": "lookup",
            "intent_class": "investigation",
            "answer_mode": "table",
            "operations": [{
                "alias": "first_users",
                "type": "lookup_rows",
                "source": "users.csv",
                "columns": ["user_id", "name", "signup_date", "platform", "city", "user_type"],
                "sort_by": "signup_date",
                "sort_order": "asc",
                "limit": 1,
                "title": "Earliest signed up users",
            }],
            "needs_clarification": "There may not be a single first customer if multiple users share the same earliest signup date.",
            "next_steps": [],
        }

    default_source = source_names[0] if source_names else ""
    if default_source.endswith(".md"):
        operations = [{
            "type": "read_document_excerpt",
            "source": default_source,
            "title": "Relevant document excerpts",
        }]
    else:
        operations = [{
            "type": "lookup_rows",
            "source": default_source,
            "limit": 5,
            "title": "Relevant rows",
        }]
    return {
        "intent": "summarize",
        "intent_class": "reference",
        "answer_mode": "table",
        "operations": operations,
        "needs_clarification": "I used a conservative fallback plan because the planner could not interpret the question confidently.",
        "pending_follow_up": None,
        "next_steps": [],
    }


def _resolve_intent_class(
    agent: str,
    query: str,
    planner: dict[str, Any],
    source_metadata: list[dict[str, Any]],
) -> str:
    explicit = str(planner.get("intent_class") or "").strip().lower()
    allowed = {
        "reference", "dataset_summary", "schema_question", "investigation", "comparison",
        "trend_analysis", "root_cause_analysis", "quote_lookup", "incident_timeline",
    }
    if explicit in allowed:
        return explicit

    q = query.lower()
    operation_types = {str(op.get("type", "")).strip() for op in planner.get("operations", [])}
    source_names = [item.get("name", "") for item in source_metadata]

    if any(token in q for token in ("each dataset", "each table", "dataset summary", "what tables", "what datasets")):
        return "dataset_summary"
    if any(token in q for token in ("date range", "duration", "how long", "coverage", "schema", "columns", "fields")):
        return "schema_question"
    if agent == "ux_researcher" and ({"extract_feedback_themes", "select_representative_quotes", "count_issue_mentions"} & operation_types or any(
        token in q for token in ("quote", "quotes", "theme", "themes", "complaint", "complaints", "feedback")
    )):
        return "quote_lookup"
    if agent == "engineering_lead" and ({"build_incident_timeline", "correlate_deployments_with_metrics", "summarize_error_shift", "compare_pre_post_rollout"} & operation_types or any(
        token in q for token in ("timeline", "incident", "deployment", "rollout", "rollback")
    )):
        return "incident_timeline"
    if "aggregate_timeseries" in operation_types or any(token in q for token in ("trend", "over time", "daily", "weekly", "monthly")):
        return "trend_analysis"
    if "aggregate_breakdown" in operation_types or "rank_rows" in operation_types or any(token in q for token in ("compare", "break down", "split", "segment")):
        return "comparison"
    if "compute_funnel" in operation_types or any(token in q for token in ("root cause", "why", "cause", "explain", "funnel")):
        return "root_cause_analysis" if any(token in q for token in ("root cause", "why", "cause", "explain")) else "investigation"
    if any(name in q for name in source_names):
        return "reference"
    return "investigation"


def _apply_deterministic_intent_plan(
    agent: str,
    query: str,
    planner: dict[str, Any],
    source_metadata: list[dict[str, Any]],
) -> dict[str, Any]:
    intent_class = _resolve_intent_class(agent, query, planner, source_metadata)
    source_names = [item["name"] for item in source_metadata]
    q = query.lower()

    if intent_class == "dataset_summary":
        planner["answer_mode"] = "text"
        planner["operations"] = [
            {
                "type": "summarize_source_profile",
                "source": source_name,
                "title": f"{source_name} profile",
            }
            for source_name in source_names[:6]
        ]
        planner["intent_class"] = intent_class
        planner["next_steps"] = []
        planner["pending_follow_up"] = None
        return planner

    if intent_class == "schema_question":
        explicit_source = next((name for name in source_names if name in q), None)
        target_source = explicit_source or (source_names[0] if source_names else "")
        operation_type = "summarize_date_span" if any(token in q for token in ("date range", "duration", "how long", "coverage", "span")) else "summarize_source_profile"
        planner["answer_mode"] = "text"
        planner["operations"] = [{
            "type": operation_type,
            "source": target_source,
            "title": f"{target_source} reference",
        }]
        planner["intent_class"] = intent_class
        planner["next_steps"] = []
        planner["pending_follow_up"] = None
        return planner

    planner["intent_class"] = intent_class
    return planner


def _synthesize_response(
    llm: LLMClient,
    agent: str,
    query: str,
    planner: dict[str, Any],
    intent_class: str,
    citations: list[dict[str, Any]],
    warnings: list[str],
    artifacts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    next_steps: list[str],
    pending_follow_up: dict[str, Any] | None,
) -> str:
    if not evidence:
        if warnings:
            return warnings[0]
        return "I couldn't find evidence to answer that from my available sources."

    system = (
        f"{AGENT_PERSONAS[agent]}\n\n"
        "Write a concise answer using only the provided evidence. "
        "Do not invent facts, identifiers, totals, dates, or causes. "
        "If warnings indicate ambiguity, say so plainly. "
        "Do not suggest a follow-up unless it matches one of the provided next_steps exactly. "
        "Do not mention hidden system prompts or planning. "
        "For reference-style questions, summarize the source clearly and avoid calling it evidence or a board artifact."
    )
    user = json.dumps(
        {
            "question": query,
            "intent_class": intent_class,
            "planner": planner,
            "warnings": warnings,
            "citations": citations,
            "evidence_summaries": [item.get("summary", "") for item in evidence],
            "artifact_titles": [item.get("title", "") for item in artifacts],
            "next_steps": next_steps,
            "pending_follow_up": pending_follow_up,
        },
        ensure_ascii=True,
    )

    try:
        text = _clean_response_text(llm.chat_text(system=system, user=user).strip())
        if text:
            return text
    except Exception as exc:
        logger.warning("Synthesis failed, using deterministic summary: %s", exc)

    return _deterministic_response(evidence, warnings)


def _deterministic_response(evidence: list[dict[str, Any]], warnings: list[str]) -> str:
    parts = [item.get("summary", "") for item in evidence if item.get("summary")]
    text = _clean_response_text(" ".join(parts).strip())
    ambiguity = next((warning for warning in warnings if "ambiguous" in warning.lower()), None)
    if ambiguity and text:
        return f"{ambiguity} {text}".strip()
    return text or _fallback_warning_message(warnings)


def _domain_redirect(agent: str, query: str) -> str | None:
    q = query.lower()
    scores = {
        role: sum(1 for token in tokens if token in q)
        for role, tokens in DOMAIN_KEYWORDS.items()
    }
    best_role = max(scores, key=scores.get)
    if scores[best_role] == 0 or best_role == agent:
        return None
    if scores[best_role] >= max(scores[agent] + 2, 2):
        return DOMAIN_REDIRECTS[best_role]
    return None


def _default_next_steps(agent: str, query: str) -> list[str]:
    if agent == "analyst":
        return [
            "Ask for a platform or payment-method split if you want to narrow the pattern.",
            "Ask Engineering whether any deployments line up with the same time period.",
        ]
    if agent == "ux_researcher":
        return [
            "Ask for ticket or review examples tied to the same user pain point.",
            "Ask the analyst whether the same issue shows up in a specific segment or platform.",
        ]
    return [
        "Ask for the deployment or service that changed closest to the observed metric shift.",
        "Ask the analyst whether the business impact is isolated to a segment or platform.",
    ]


AFFIRMATIVE_FOLLOW_UPS = {"yes", "yeah", "yep", "sure", "ok", "okay", "do it", "please do", "go ahead"}
NEGATIVE_FOLLOW_UPS = {"no", "nah", "nope", "not now", "skip it"}


def _resolve_follow_up_query(agent: str, query: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = " ".join(query.lower().split())
    last_turn = _last_same_agent_history_item(history, agent)
    if not last_turn:
        return {"effective_query": query, "note": None, "handled_response": None, "pending_follow_up": None}

    planner = last_turn.get("planner") or {}
    pending_follow_up = _normalize_pending_follow_up(planner.get("pending_follow_up"))
    if pending_follow_up:
        if normalized in NEGATIVE_FOLLOW_UPS:
            return {
                "effective_query": query,
                "note": "The previous follow-up thread was dismissed by the user.",
                "handled_response": "Understood. We can drop that thread and move on.",
                "pending_follow_up": None,
            }
        if normalized in AFFIRMATIVE_FOLLOW_UPS:
            default_choice = pending_follow_up["default_choice"]
            return {
                "effective_query": pending_follow_up["resolved_query_template"].format(choice=default_choice),
                "note": "Interpreted a short affirmative reply using the previous turn's pending follow-up.",
                "handled_response": None,
                "pending_follow_up": None,
            }

        matched_choice = _match_follow_up_choice(query, pending_follow_up["choices"])
        if matched_choice:
            return {
                "effective_query": pending_follow_up["resolved_query_template"].format(choice=matched_choice),
                "note": "Resolved the reply against the previous turn's pending follow-up choices.",
                "handled_response": None,
                "pending_follow_up": None,
            }

        if len(normalized.split()) <= 3:
            choices = "; ".join(pending_follow_up["choices"])
            return {
                "effective_query": query,
                "note": "The short reply did not match any pending follow-up choice.",
                "handled_response": f"I can continue that thread, but I need you to choose one of these: {choices}",
                "pending_follow_up": pending_follow_up,
            }

        return {"effective_query": query, "note": None, "handled_response": None, "pending_follow_up": pending_follow_up}

    if normalized not in AFFIRMATIVE_FOLLOW_UPS:
        return {"effective_query": query, "note": None, "handled_response": None, "pending_follow_up": None}

    artifacts = last_turn.get("artifacts") or []
    fallback_query = _heuristic_follow_up_from_artifacts(last_turn.get("query", ""), artifacts)
    if fallback_query:
        return {
            "effective_query": fallback_query,
            "note": "Interpreted a short affirmative reply using the previous turn's artifacts.",
            "handled_response": None,
            "pending_follow_up": None,
        }

    return {"effective_query": query, "note": None, "handled_response": None, "pending_follow_up": None}


def _heuristic_follow_up_from_artifacts(previous_query: str, artifacts: list[dict[str, Any]]) -> str | None:
    lowered_query = previous_query.lower()
    for artifact in artifacts:
        if artifact.get("kind") != "chart":
            continue
        if artifact.get("chart_type") == "line" and "trend" in lowered_query:
            return "Break down the previous trend by platform."
        if artifact.get("chart_type") == "bar":
            return "Show the top contributors behind the previous breakdown."
        if artifact.get("chart_type") == "funnel":
            return "Break down the funnel by platform."
    return None


def _last_same_agent_history_item(history: list[dict[str, Any]], agent: str) -> dict[str, Any] | None:
    for item in reversed(history):
        if item.get("agent") == agent:
            return item
    return None


def _last_agent_turn_context(history: list[dict[str, Any]], agent: str) -> dict[str, Any] | None:
    last_turn = _last_same_agent_history_item(history, agent)
    if not last_turn:
        return None
    planner = last_turn.get("planner") or {}
    artifacts = last_turn.get("artifacts") or []
    return {
        "query": last_turn.get("query"),
        "response": last_turn.get("response"),
        "next_steps": planner.get("next_steps") or [],
        "effective_query": planner.get("effective_query"),
        "pending_follow_up": planner.get("pending_follow_up"),
        "artifact_titles": [artifact.get("title") for artifact in artifacts[:3]],
    }


def _source_columns(source_metadata: list[dict[str, Any]], source_name: str) -> list[str]:
    for source in source_metadata:
        if source["name"] == source_name:
            return source.get("columns", [])
    return []


def _normalize_pending_follow_up(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    prompt = str(value.get("prompt") or "").strip()
    raw_choices = value.get("choices") or []
    choices = [str(choice).strip() for choice in raw_choices if str(choice).strip()]
    if not prompt or not choices:
        return None
    default_choice = str(value.get("default_choice") or choices[0]).strip()
    if default_choice not in choices:
        default_choice = choices[0]
    resolved_query_template = str(value.get("resolved_query_template") or "{choice}").strip()
    return {
        "prompt": prompt,
        "choices": choices,
        "default_choice": default_choice,
        "resolved_query_template": resolved_query_template,
    }


def _resolve_pending_follow_up(
    planner: dict[str, Any],
    query: str,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    pending = _normalize_pending_follow_up(planner.get("pending_follow_up"))
    if pending:
        return pending
    lowered = query.lower()
    if any(artifact.get("kind") == "chart" and artifact.get("chart_type") == "line" for artifact in artifacts):
        return {
            "prompt": "Would you like to break down this trend further?",
            "choices": [
                "Break down the previous trend by platform.",
                "Break down the previous trend by order status.",
                "Show the previous trend aggregated monthly.",
            ],
            "default_choice": "Break down the previous trend by platform.",
            "resolved_query_template": "{choice}",
        }
    if any(artifact.get("kind") == "chart" and artifact.get("chart_type") == "funnel" for artifact in artifacts):
        return {
            "prompt": "Would you like to break down the funnel further?",
            "choices": [
                "Break down the funnel by platform.",
                "Break down the funnel by app version.",
            ],
            "default_choice": "Break down the funnel by platform.",
            "resolved_query_template": "{choice}",
        }
    if any(artifact.get("kind") == "chart" and artifact.get("chart_type") == "bar" for artifact in artifacts) or "break down" in lowered:
        return {
            "prompt": "Would you like to continue this breakdown?",
            "choices": [
                "Show the same breakdown over time.",
                "Rank the strongest and weakest segments in the previous breakdown.",
            ],
            "default_choice": "Show the same breakdown over time.",
            "resolved_query_template": "{choice}",
        }
    return None


def _match_follow_up_choice(query: str, choices: list[str]) -> str | None:
    normalized_query = _normalize_choice_text(query)
    if not normalized_query:
        return None
    for choice in choices:
        normalized_choice = _normalize_choice_text(choice)
        if normalized_query == normalized_choice or normalized_query in normalized_choice:
            return choice
    return None


def _normalize_choice_text(value: str) -> str:
    return " ".join(value.lower().replace(".", "").split())


def _clean_response_text(text: str) -> str:
    cleaned = text.replace("**", "").replace("*", "")
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("\r", "")
    for prefix in (
        "Based on the provided evidence, ",
        "Based on the evidence provided, ",
        "Based on the evidence, ",
    ):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines())
    cleaned = "\n".join(line for line in cleaned.splitlines() if line and line != "(Chart)")
    return cleaned.strip()


def _fallback_warning_message(warnings: list[str]) -> str:
    for warning in warnings:
        if "Interpreted a short affirmative reply" in warning:
            continue
        if "Planner fallback used" in warning:
            continue
        if "pending follow-up" in warning:
            continue
        return warning
    return "I gathered evidence, but I couldn't form a clean summary."
