"""Agent router — iterative role-based investigation over scoped SQL access."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Callable

from data_layer.db import (
    execute_authorized_select,
    get_document,
    get_table_date_ranges,
    get_distinct_value_previews,
    get_sample_rows,
    get_table_columns,
    get_table_row_count,
    get_table_schema,
)
from llm_interface.llm_client import LLMClient
from scenario_loader.loader import get_agent_role_config
from telemetry_layer.telemetry import VALID_AGENTS

logger = logging.getLogger(__name__)

MAX_HISTORY_ITEMS = 12
MAX_INVESTIGATION_ATTEMPTS = 4
MAX_TABLE_RESULT_ROWS = 200
MAX_CHART_RESULT_ROWS = 10000
MAX_CLARIFICATION_QUESTIONS = 3

PLAN_SCHEMA = {
    "question_understanding": "Short summary of the user's ask",
    "complexity": "single_query | multi_step",
    "sub_questions": ["Optional sub-question"],
    "target_tables": ["Allowed source name such as orders"],
    "stop_condition": "What evidence is enough to answer",
    "next_steps": ["Follow-up the user might ask next"],
    "needs_clarification": False,
    "clarification_reason": "Why a clarification is required before reliable analysis",
    "pending_follow_up": {
        "prompt": "Single clarifying question to ask the user",
        "choices": ["Suggested reply"],
        "default_choice": "Recommended reply",
        "resolved_query_template": "{original_question} by {choice}",
        "allow_free_text": True,
    },
}

ACTION_SCHEMA = {
    "action": "sql | python | document | finish",
    "reason": "Short rationale",
    "sql": "Read-only SQL query when action is sql or python",
    "python_code": "Pandas code when action is python. Operates on df (DataFrame from sql). Must assign result = <final DataFrame>. Only pd (pandas) and np (numpy) are available.",
    "document": "Allowed markdown source name when action is document",
    "document_terms": ["Optional search terms for document excerpts"],
    "title": "Human-friendly title for the resulting evidence",
    "answer_mode": "metric | chart | table | text",
    "chart_type": (
        "Optional when answer_mode=chart. Choose the most appropriate type: "
        "bar (categorical comparisons, rankings, top-N), "
        "line (trends over time, continuous data), "
        "funnel (sequential steps with drop-off), "
        "pie (proportions/share of total, max 8 slices), "
        "scatter (correlation between two numeric variables), "
        "heatmap (matrix of values, cross-tabs, cohort grids), "
        "histogram (distribution of a single numeric variable), "
        "box (statistical spread: min/Q1/median/Q3/max), "
        "dual_axis_line (two metrics with very different scales on same time axis)"
    ),
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
    status_callback: Callable[[dict[str, str]], None] | None = None,
) -> dict[str, Any]:
    """Plan an investigation, execute scoped queries, and synthesize the answer."""
    validate_agent(agent)
    history = conversation_history or []

    def _emit(stage: str, detail: str = "") -> None:
        if status_callback:
            status_callback({"stage": stage, "detail": detail})

    role = get_agent_role_config(scenario_id, agent)
    source_metadata = _build_source_metadata(
        scenario_id,
        role["allowed_tables"],
        role.get("allowed_documents", []),
    )
    conversation_context = _build_conversation_context(history)
    clarification_state = _clarification_state(history, agent)
    clarification_resolution = _resolve_clarification_reply(query, clarification_state)
    original_query = clarification_resolution["original_query"] or query
    effective_query = clarification_resolution["effective_query"] or query
    clarification_history = clarification_resolution["clarification_history"]

    _route_start_ms = time.monotonic()
    _emit("planning", "Understanding your question and planning investigation...")
    plan, plan_warning = _plan_investigation(
        llm=llm,
        agent=agent,
        role=role,
        query=effective_query,
        original_query=original_query,
        source_metadata=source_metadata,
        conversation_context=conversation_context,
        clarification_state=clarification_state,
        clarification_resolution=clarification_resolution,
    )
    plan = _finalize_plan_clarification_state(
        plan=plan,
        original_query=original_query,
        effective_query=effective_query,
        prior_clarification_count=clarification_state["clarification_count"],
        clarification_history=clarification_history,
    )
    clarification_warning = _clarification_cap_warning(plan, clarification_state["clarification_count"])
    if clarification_warning:
        warnings_seed = [clarification_warning]
        plan["pending_follow_up"] = None
        plan["needs_clarification"] = False
    else:
        warnings_seed = []

    if plan.get("pending_follow_up"):
        response = _clarification_response(plan)
        warnings = warnings_seed[:]
        if plan_warning:
            warnings.append(plan_warning)
        if clarification_resolution.get("note"):
            warnings.append(clarification_resolution["note"])
        return {
            "agent": agent,
            "response": response,
            "artifacts": [],
            "citations": [],
            "warnings": _unique_preserve(warnings),
            "next_steps": plan.get("next_steps") or [],
            "pending_follow_up": plan.get("pending_follow_up"),
            "intent_class": "investigation",
            "_planner": plan,
            "_attempts": [],
        }

    _emit("investigating", "Starting data investigation...")
    evidence, attempts, warnings = _run_investigation_loop(
        llm=llm,
        scenario_id=scenario_id,
        agent=agent,
        role=role,
        query=effective_query,
        plan=plan,
        source_metadata=source_metadata,
        conversation_context=conversation_context,
        status_callback=status_callback,
    )
    warnings = warnings_seed + warnings
    if plan_warning:
        warnings.append(plan_warning)
    if clarification_resolution.get("note"):
        warnings.append(clarification_resolution["note"])

    _emit("synthesizing", "Composing final answer...")
    artifacts, citations = _build_artifacts_and_citations(evidence, agent)
    response = _synthesize_response(
        llm=llm,
        agent=agent,
        role=role,
        query=original_query,
        plan=plan,
        evidence=evidence,
        warnings=warnings,
        conversation_context=conversation_context,
    )

    total_duration_ms = round((time.monotonic() - _route_start_ms) * 1000)
    trace = {
        "intent": query,
        "effective_query": effective_query if effective_query != query else None,
        "conversation_turns": len(history),
        "clarification_asked": clarification_resolution.get("latest_reply"),
        "clarification_resolved": bool(clarification_resolution.get("effective_query")),
        "plan_complexity": plan.get("complexity", "single_query"),
        "total_attempts": len(attempts),
        "evidence_collected": len(evidence),
        "total_duration_ms": total_duration_ms,
    }
    return {
        "agent": agent,
        "response": response,
        "artifacts": artifacts,
        "citations": citations,
        "warnings": _unique_preserve(warnings),
        "next_steps": plan.get("next_steps") or _default_next_steps(role),
        "pending_follow_up": plan.get("pending_follow_up"),
        "intent_class": "investigation",
        "_planner": {**plan, "conversation_context_summary": conversation_context, "attempt_count": len(attempts)},
        "_attempts": attempts,
        "_trace": trace,
    }


def _plan_investigation(
    llm: LLMClient,
    agent: str,
    role: dict[str, Any],
    query: str,
    original_query: str,
    source_metadata: list[dict[str, Any]],
    conversation_context: list[dict[str, Any]],
    clarification_state: dict[str, Any],
    clarification_resolution: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    system = _role_system_prompt(agent, role) + (
        "\n\nCreate a short investigation plan before querying data. "
        "Decide whether the question looks solvable with one query or needs multiple steps. "
        "Use the provided table metadata, including distinct categorical values, to resolve likely filters before asking the user. "
        "If metadata is not enough, prefer a small discovery query over a clarifying question. "
        "For trend or time-series questions, plan to use the full available date range unless the user explicitly narrows it. "
        "You have the full conversation history including previous queries, responses, and SQL. "
        "If the current question is short or references prior results (e.g., 'not aggregated', "
        "'show as time series', 'break it down by city'), treat it as a follow-up refinement of the "
        "previous query — combine the prior context with the current request to form a complete plan. "
        "Do not ask for clarification when the conversation history provides sufficient context. "
        "Ask a clarifying question only when the ambiguity materially changes the SQL plan or answer semantics. "
        "Ask one clarifying question at a time, prefer 2-3 suggested answers for common ambiguities, "
        "always allow free-text clarification, and do not ask more questions if the clarification budget is exhausted. "
        "Return JSON only."
    )
    plan, error = _chat_json(
        llm=llm,
        system=system,
        payload={
            "question": query,
            "original_question": original_query,
            "allowed_sources": source_metadata,
            "conversation_history": conversation_context,
            "clarification_state": {
                "clarification_count": clarification_state["clarification_count"],
                "clarification_budget_remaining": max(0, MAX_CLARIFICATION_QUESTIONS - clarification_state["clarification_count"]),
                "clarification_history": clarification_resolution["clarification_history"],
                "unresolved_pending_follow_up": clarification_state.get("pending_follow_up"),
                "latest_user_reply": clarification_resolution.get("latest_reply"),
            },
            "response_schema": PLAN_SCHEMA,
        },
        normalize=lambda value: _normalize_plan(value, source_metadata),
        purpose="planner",
    )
    if plan is not None:
        return plan, None
    return _generic_plan(source_metadata), f"Planner could not produce valid structured output: {error}"


def _run_investigation_loop(
    llm: LLMClient,
    scenario_id: str,
    agent: str,
    role: dict[str, Any],
    query: str,
    plan: dict[str, Any],
    source_metadata: list[dict[str, Any]],
    conversation_context: list[dict[str, Any]],
    status_callback: Callable[[dict[str, str]], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    attempts: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    allowed_sql_tables = set(role.get("allowed_tables", []))

    def _emit(stage: str, detail: str = "") -> None:
        if status_callback:
            status_callback({"stage": stage, "detail": detail})

    for attempt_no in range(1, MAX_INVESTIGATION_ATTEMPTS + 1):
        _emit("choosing_action", f"Attempt {attempt_no}: selecting next action...")
        action, action_warning = _choose_next_action(
            llm=llm,
            agent=agent,
            role=role,
            query=query,
            plan=plan,
            source_metadata=source_metadata,
            conversation_context=conversation_context,
            attempts=attempts,
            evidence=evidence,
        )
        if action_warning:
            warnings.append(action_warning)

        action_type = action.get("action")
        if action_type == "finish":
            break

        _step_start_ms = time.monotonic()
        if action_type == "document":
            _emit("searching_docs", f"Searching documents: {action.get('title', '')}")
            record = _execute_document_step(
                scenario_id=scenario_id,
                action=action,
                allowed_sources=role.get("allowed_documents", []),
                query=query,
            )
        elif action_type == "python":
            _emit("executing_python", f"Running pandas analysis: {action.get('title', '')}")
            record = _execute_python_step(
                scenario_id=scenario_id,
                action=action,
                allowed_sql_tables=allowed_sql_tables,
            )
        else:
            _emit("executing_sql", f"Running SQL query: {action.get('title', '')}")
            record = _execute_sql_step(
                scenario_id=scenario_id,
                action=action,
                allowed_sql_tables=allowed_sql_tables,
            )

        record["attempt"] = attempt_no
        record["duration_ms"] = round((time.monotonic() - _step_start_ms) * 1000)
        record["rows_returned"] = len(record.get("rows") or [])
        attempts.append(record)

        if record["status"] == "success" and record.get("rows"):
            # Critic check — validate result quality before accepting
            _emit("critic_review", f"Checking query quality (attempt {attempt_no})...")
            is_ok, rejection_reason, suggested_fix = _critic_check(
                llm=llm, query=query, action=action, record=record, plan=plan
            )
            # Always record critic feedback on the attempt record
            record["critic_ok"] = is_ok
            if rejection_reason:
                record["critic_reason"] = rejection_reason
            if suggested_fix:
                record["critic_fix"] = suggested_fix
            if not is_ok:
                record["status"] = "rejected"
                record["rejection_reason"] = rejection_reason
                record["suggested_fix"] = suggested_fix
                _emit("critic_rejected", f"Critic rejected: {(rejection_reason or '')[:100]}")
                continue

            evidence.append(
                {
                    "evidence_id": f"ev_{uuid.uuid4().hex[:8]}",
                    "title": record.get("title") or f"Attempt {attempt_no}",
                    "rows": record.get("rows", []),
                    "columns": record.get("columns", []),
                    "answer_mode": record.get("answer_mode", "table"),
                    "chart_type": record.get("chart_type"),
                    "summary": _summarize_attempt(record),
                    "sources": record.get("sources", []),
                    "query": record.get("sql"),
                    "kind": record.get("kind"),
                    "truncated": record.get("truncated", False),
                }
            )
            if plan.get("complexity") == "single_query":
                break
            continue

        if record["status"] == "error":
            warnings.append(record.get("error") or "Query attempt failed.")
            continue

        if record["status"] == "success" and not record.get("rows"):
            warnings.append(f"{record.get('title') or 'Query attempt'} returned no rows.")

    if not evidence and attempts:
        warnings.append("The agent could not find strong evidence within the allowed attempt limit.")
    return evidence, attempts, warnings


def _choose_next_action(
    llm: LLMClient,
    agent: str,
    role: dict[str, Any],
    query: str,
    plan: dict[str, Any],
    source_metadata: list[dict[str, Any]],
    conversation_context: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> tuple[dict[str, Any], str | None]:
    if attempts and evidence:
        return {"action": "finish", "reason": "We already have evidence.", "title": "Final answer", "answer_mode": "text"}, None

    system = _role_system_prompt(agent, role) + (
        "\n\nYou are in an investigation loop. "
        "Choose the next best step to answer the question. "
        "If the user mentioned a segment or category that might match a low-cardinality column, check metadata or run a small discovery query before asking for clarification. "
        "For trend or time-series questions, use answer_mode=chart and query the full available date range unless the user explicitly asks for a narrower window. "
        "Choose answer_mode and chart_type based on query intent: "
        "use answer_mode=metric for single-value questions (total, first, max, which X); "
        "use chart_type=line for trends over time; "
        "use chart_type=bar for categorical comparisons and rankings; "
        "use chart_type=funnel for sequential stage drop-off; "
        "use chart_type=pie for proportions/share of total (only when ≤8 categories); "
        "use chart_type=scatter when the user asks about correlation between two numeric variables; "
        "use chart_type=heatmap for matrix/cross-tab/cohort data; "
        "use chart_type=histogram when showing distribution of a single numeric variable; "
        "use chart_type=box for statistical spread (min/max/quartiles); "
        "use chart_type=dual_axis_line when comparing two metrics with very different scales on the same time axis. "
        "Do not add arbitrary recent-day limits to trend queries. "
        "For weekly aggregations in SQLite, always use strftime('%Y-%m-%d', date_col, 'weekday 0', '-6 days') "
        "to get the Monday (week start) date, and GROUP BY that expression. "
        "Do NOT use strftime('%W') or strftime('%Y-W%W') as these create duplicates at year boundaries. "
        "Use action=python when the question requires transformations SQL cannot easily express: "
        "rolling averages, percentiles, percentage-of-total, complex pivots, multi-step reshaping. "
        "When using action=python, provide BOTH sql (to fetch raw data) and python_code (pandas transformation). "
        "The python_code receives a DataFrame called `df` and must assign the final result to `result`. "
        "Only pd (pandas) and np (numpy) are available. "
        "For simple aggregations, filtering, or joins, prefer action=sql. "
        "If you already have enough evidence, return action=finish. "
        "Return JSON only."
    )
    action, error = _chat_json(
        llm=llm,
        system=system,
        payload={
            "question": query,
            "plan": plan,
            "allowed_sources": source_metadata,
            "conversation_context": conversation_context,
            "attempts_so_far": attempts,
            "evidence_summaries": [item["summary"] for item in evidence],
            "response_schema": ACTION_SCHEMA,
        },
        normalize=lambda value: _normalize_action(value, plan, source_metadata),
        purpose="action selector",
    )
    if action is not None:
        return action, None
    return {"action": "finish", "reason": "No valid next step could be produced.", "title": "Final answer", "answer_mode": "text"}, f"Action selection failed: {error}"


def _execute_sql_step(
    scenario_id: str,
    action: dict[str, Any],
    allowed_sql_tables: set[str],
) -> dict[str, Any]:
    sql = str(action.get("sql") or "").strip()
    result = execute_authorized_select(
        scenario_id=scenario_id,
        sql=sql,
        allowed_tables=allowed_sql_tables,
        max_rows=MAX_CHART_RESULT_ROWS if action.get("answer_mode") == "chart" else MAX_TABLE_RESULT_ROWS,
    )
    if not result["ok"]:
        return {
            "status": "error",
            "kind": "sql",
            "title": action.get("title") or "SQL attempt",
            "answer_mode": action.get("answer_mode", "table"),
            "chart_type": action.get("chart_type"),
            "sql": sql,
            "error": result["error"],
            "sources": result.get("referenced_tables", []),
            "columns": [],
            "rows": [],
            "truncated": False,
        }
    return {
        "status": "success",
        "kind": "sql",
        "title": action.get("title") or "SQL result",
        "answer_mode": action.get("answer_mode", "table"),
        "chart_type": action.get("chart_type"),
        "sql": result["executed_sql"],
        "sources": result.get("referenced_tables", []),
        "columns": result["columns"],
        "rows": result["rows"],
        "truncated": result["truncated"],
    }


def _execute_python_step(
    scenario_id: str,
    action: dict[str, Any],
    allowed_sql_tables: set[str],
) -> dict[str, Any]:
    """Execute SQL to fetch data, then apply pandas transformation."""
    from .sandbox import execute_pandas_code

    sql = str(action.get("sql") or "").strip()
    python_code = str(action.get("python_code") or "").strip()

    # Step 1: run SQL through existing validated pipeline
    sql_result = execute_authorized_select(
        scenario_id=scenario_id,
        sql=sql,
        allowed_tables=allowed_sql_tables,
        max_rows=MAX_CHART_RESULT_ROWS,  # fetch more rows for pandas to work with
    )
    if not sql_result["ok"]:
        return {
            "status": "error",
            "kind": "python",
            "title": action.get("title") or "Python attempt",
            "answer_mode": action.get("answer_mode", "table"),
            "chart_type": action.get("chart_type"),
            "sql": sql,
            "python_code": python_code,
            "error": f"SQL step failed: {sql_result['error']}",
            "sources": sql_result.get("referenced_tables", []),
            "columns": [],
            "rows": [],
            "truncated": False,
        }

    # Step 2: convert SQL result to DataFrame
    import pandas as pd

    df = pd.DataFrame(sql_result["rows"], columns=sql_result["columns"])

    # Step 3: run pandas code in sandbox
    sandbox_result = execute_pandas_code(python_code, df)
    if not sandbox_result["ok"]:
        return {
            "status": "error",
            "kind": "python",
            "title": action.get("title") or "Python attempt",
            "answer_mode": action.get("answer_mode", "table"),
            "chart_type": action.get("chart_type"),
            "sql": sql,
            "python_code": python_code,
            "error": f"Pandas step failed: {sandbox_result['error']}",
            "sources": sql_result.get("referenced_tables", []),
            "columns": sql_result["columns"],
            "rows": sql_result["rows"],
            "truncated": sql_result["truncated"],
        }

    return {
        "status": "success",
        "kind": "python",
        "title": action.get("title") or "Python result",
        "answer_mode": action.get("answer_mode", "table"),
        "chart_type": action.get("chart_type"),
        "sql": sql,
        "python_code": python_code,
        "sources": sql_result.get("referenced_tables", []),
        "columns": sandbox_result["columns"],
        "rows": sandbox_result["rows"],
        "truncated": sandbox_result["truncated"],
    }


def _critic_check(
    llm: LLMClient,
    query: str,
    action: dict[str, Any],
    record: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    """Review SQL/Python code for correctness before accepting results as evidence.

    Returns (is_acceptable, rejection_reason, suggested_fix).
    """
    columns = record.get("columns", [])
    sql = record.get("sql") or action.get("sql") or ""

    system = (
        "You are a SQL/code quality reviewer. Given a user question and the SQL query "
        "(and optional Python/pandas code) that was generated to answer it, determine if "
        "the code is logically correct.\n\n"
        "Only reject if there is a CLEAR, SPECIFIC error such as:\n"
        "- Syntax errors in SQL or Python code\n"
        "- Wrong GROUP BY granularity (e.g., daily when weekly was asked, or vice versa)\n"
        "- Missing or incorrect JOIN conditions that would produce wrong results\n"
        "- Filters that exclude data the user explicitly asked about\n"
        "- Week grouping using strftime('%W') or '%Y-W%W' instead of week-start dates\n"
        "- Aggregation errors (e.g., SUM when COUNT was needed)\n\n"
        "Do NOT reject for stylistic preferences, minor optimizations, or speculative issues.\n"
        "When in doubt, mark it acceptable. The bar for rejection should be high — "
        "only reject when the query will produce WRONG results for the user's question.\n\n"
        "Respond with JSON only: {\"acceptable\": true/false, \"reason\": \"...\", \"suggested_fix\": \"...\"}"
    )

    payload = {
        "question": query,
        "sql": sql,
        "python_code": record.get("python_code") or action.get("python_code") or "",
        "answer_mode": record.get("answer_mode", "table"),
        "columns": columns,
        "plan_context": plan.get("question_understanding", ""),
    }

    def _normalize_critic(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "acceptable": bool(value.get("acceptable", True)),
            "reason": str(value.get("reason") or "").strip(),
            "suggested_fix": str(value.get("suggested_fix") or "").strip(),
        }

    try:
        result, error = _chat_json(
            llm=llm,
            system=system,
            payload=payload,
            normalize=_normalize_critic,
            purpose="result critic",
        )
        if result is None:
            # If critic call fails, accept the result (don't block on critic errors)
            logger.warning("Critic check failed: %s — accepting result", error)
            return True, None, None

        if result["acceptable"]:
            logger.info("Critic accepted: SQL looks correct for question")
            return True, None, None

        reason = result["reason"] or "Result quality issue detected"
        fix = result["suggested_fix"] or None
        logger.info("Critic rejected: %s | Suggested fix: %s", reason, fix)
        return False, reason, fix
    except Exception as exc:
        logger.warning("Critic check exception: %s — accepting result", exc)
        return True, None, None


def _execute_document_step(
    scenario_id: str,
    action: dict[str, Any],
    allowed_sources: list[str],
    query: str,
) -> dict[str, Any]:
    source = str(action.get("document") or "").strip()
    if source not in allowed_sources or not source.endswith(".md"):
        return {
            "status": "error",
            "kind": "document",
            "title": action.get("title") or "Document lookup",
            "answer_mode": "table",
            "error": f"Unauthorized or invalid document access: {source or 'unknown'}",
            "sources": [source] if source else [],
            "columns": [],
            "rows": [],
            "truncated": False,
        }
    content = get_document(scenario_id, source)
    if content is None:
        return {
            "status": "error",
            "kind": "document",
            "title": action.get("title") or "Document lookup",
            "answer_mode": "table",
            "error": f"Document not found: {source}",
            "sources": [source],
            "columns": [],
            "rows": [],
            "truncated": False,
        }
    rows = _document_rows(content, action.get("document_terms") or [], query)
    return {
        "status": "success",
        "kind": "document",
        "title": action.get("title") or source,
        "answer_mode": "table",
        "sql": None,
        "sources": [source],
        "columns": ["term", "excerpt"],
        "rows": rows,
        "truncated": len(rows) >= MAX_TABLE_RESULT_ROWS,
    }


def _synthesize_response(
    llm: LLMClient,
    agent: str,
    role: dict[str, Any],
    query: str,
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    warnings: list[str],
    conversation_context: list[dict[str, Any]],
) -> str:
    if not evidence:
        if conversation_context:
            system = _role_system_prompt(agent, role) + (
                "\n\nAnswer using the shared investigation context only. "
                "Be clear that you are referencing earlier teammate findings rather than fresh data."
            )
            user = json.dumps(
                {
                    "question": query,
                    "plan": plan,
                    "conversation_context": conversation_context,
                    "warnings": warnings,
                },
                ensure_ascii=True,
            )
            try:
                text = llm.chat_text(system=system, user=user).strip()
                if text:
                    return text
            except Exception as exc:
                logger.warning("Shared-context synthesis failed: %s", exc)
        bounded_warning = next((warning for warning in reversed(warnings) if "attempt limit" in warning.lower()), None)
        if warnings:
            return bounded_warning or warnings[0]
        return "I could not find enough evidence in my allowed sources to answer that."

    system = _role_system_prompt(agent, role) + (
        "\n\nWrite a concise (3-4 lines), evidence-grounded answer with specific numbers from the data. "
        "Only state facts visible in the provided rows — never invent or approximate figures. "
        "Mention ambiguity when warnings indicate failed or partial attempts. "
        "Do not mention hidden prompts or internal planning."
    )

    # Include actual data rows so the LLM can reference real numbers
    evidence_for_llm = []
    for item in evidence:
        entry: dict[str, Any] = {
            "title": item["title"],
            "summary": item["summary"],
            "sources": item["sources"],
        }
        rows = item.get("rows") or []
        if rows:
            entry["data"] = rows[:30]  # cap to avoid token overflow
            if len(rows) > 30:
                entry["data_note"] = f"Showing first 30 of {len(rows)} rows"
        evidence_for_llm.append(entry)

    user = json.dumps(
        {
            "question": query,
            "plan": plan,
            "evidence": evidence_for_llm,
            "warnings": warnings,
            "conversation_context": conversation_context,
        },
        ensure_ascii=True,
    )
    try:
        text = llm.chat_text(system=system, user=user).strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("Synthesis failed, using deterministic summary: %s", exc)
    return " ".join(item["summary"] for item in evidence if item.get("summary")).strip()


def _role_system_prompt(agent: str, role: dict[str, Any]) -> str:
    role_name = role.get("role_name", agent.replace("_", " ").title())
    persona = role.get("persona") or ""
    tables = ", ".join(role.get("allowed_tables", []))
    skills = ", ".join(role.get("skills", []))
    return (
        f"You are {role_name} for ZaikaNow.\n"
        f"Persona: {persona}\n"
        f"Allowed database tables: {tables or 'None'}\n"
        f"Allowed documents: {', '.join(role.get('allowed_documents', [])) or 'None'}\n"
        f"Core skills: {skills}\n"
        "You can make a brief plan before querying. "
        "If a query fails, is empty, or only partially answers the question, revise your approach and try again. "
        "If the user's request is materially ambiguous, you may ask one clarifying question at a time. "
        "Before asking for clarification, inspect the provided schema, sample rows, distinct categorical values, "
        "and, if needed, use a small discovery query to resolve the ambiguity from the database. "
        "For trend or time-series questions, use the full available date range from the metadata unless the user explicitly asks for a narrower window. "
        "For weekly aggregations, use strftime('%Y-%m-%d', date_col, 'weekday 0', '-6 days') to get week-start dates and GROUP BY that. "
        "Never use strftime('%W') or '%Y-W%W' for weekly grouping as they break at year boundaries. "
        "Stay within evidence from your allowed sources only."
    )


def _build_source_metadata(
    scenario_id: str,
    allowed_tables: list[str],
    allowed_documents: list[str],
) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for table in allowed_tables:
        schema = get_table_schema(scenario_id, table)
        metadata.append(
            {
                "name": table,
                "type": "table",
                "columns": get_table_columns(scenario_id, table),
                "schema": schema,
                "row_count": get_table_row_count(scenario_id, table),
                "sample_rows": get_sample_rows(scenario_id, table, 3),
                "distinct_value_previews": get_distinct_value_previews(scenario_id, table),
                "date_ranges": get_table_date_ranges(scenario_id, table),
            }
        )
    for source in allowed_documents:
        preview = (get_document(scenario_id, source) or "")[:240].replace("\n", " ").strip()
        metadata.append({"name": source, "type": "document", "preview": preview})
    return metadata


def _build_conversation_context(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build full conversation context with SQL queries and responses.

    Includes SQL/columns/row-count from prior attempts but NOT data rows
    to keep context lightweight.
    """
    context: list[dict[str, Any]] = []
    for item in history[-MAX_HISTORY_ITEMS:]:
        attempts = item.get("attempts") or []
        sql_queries = []
        for attempt in attempts:
            if attempt.get("query"):
                sql_queries.append({
                    "sql": attempt["query"],
                    "columns": attempt.get("columns"),
                    "row_count": len(attempt.get("rows") or []),
                })
        context.append({
            "agent": item.get("agent"),
            "question": item.get("query"),
            "response": item.get("response"),
            "sql_queries": sql_queries,
            "artifact_titles": [artifact.get("title") for artifact in (item.get("artifacts") or [])[:3]],
        })
    return context


def _normalize_plan(plan: dict[str, Any], source_metadata: list[dict[str, Any]]) -> dict[str, Any]:
    allowed_sources = {item["name"] for item in source_metadata}
    raw_target_tables = plan.get("target_tables") or []
    raw_sub_questions = plan.get("sub_questions") or []
    raw_next_steps = plan.get("next_steps") or []
    complexity = str(plan.get("complexity") or "single_query").strip().lower()
    if complexity not in {"single_query", "multi_step"}:
        complexity = "single_query"
    target_tables = [
        source for source in raw_target_tables if isinstance(source, str) and source in allowed_sources
    ]
    if not target_tables and source_metadata:
        target_tables = [source_metadata[0]["name"]]
    next_steps = [str(step).strip() for step in raw_next_steps if str(step).strip()][:3]
    return {
        "question_understanding": str(plan.get("question_understanding") or "").strip() or "Answer the user's question from allowed sources.",
        "complexity": complexity,
        "sub_questions": [str(item).strip() for item in raw_sub_questions if str(item).strip()][:4],
        "target_tables": target_tables,
        "stop_condition": str(plan.get("stop_condition") or "").strip() or "Stop when the answer is supported by query results.",
        "next_steps": next_steps,
        "needs_clarification": bool(plan.get("needs_clarification") or plan.get("pending_follow_up")),
        "clarification_reason": str(plan.get("clarification_reason") or "").strip(),
        "pending_follow_up": _normalize_pending_follow_up(plan.get("pending_follow_up")),
    }


def _normalize_action(action: dict[str, Any], plan: dict[str, Any], source_metadata: list[dict[str, Any]]) -> dict[str, Any]:
    allowed_sources = {item["name"] for item in source_metadata}
    raw_document_terms = action.get("document_terms") or []
    action_type = str(action.get("action") or "sql").strip().lower()
    if action_type not in {"sql", "python", "document", "finish"}:
        action_type = "sql"
    python_code = str(action.get("python_code") or "").strip()
    if action_type == "python" and not python_code:
        action_type = "sql"  # fall back if no code provided
    answer_mode = str(action.get("answer_mode") or "table").strip().lower()
    if answer_mode not in {"metric", "chart", "table", "text"}:
        answer_mode = "table"
    chart_type = _normalize_chart_type(action.get("chart_type")) if answer_mode == "chart" else None
    document = str(action.get("document") or "").strip()
    if document and document not in allowed_sources:
        document = ""
    return {
        "action": action_type,
        "reason": str(action.get("reason") or "").strip(),
        "sql": str(action.get("sql") or "").strip(),
        "python_code": python_code,
        "document": document,
        "document_terms": [str(term).strip() for term in raw_document_terms if str(term).strip()][:3],
        "title": str(action.get("title") or "").strip() or "Investigation result",
        "answer_mode": answer_mode,
        "chart_type": chart_type,
        "target_tables": plan.get("target_tables", []),
    }


def _generic_plan(source_metadata: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "question_understanding": "Investigate the question using allowed sources and revise based on query results.",
        "complexity": "multi_step",
        "sub_questions": [],
        "target_tables": [item["name"] for item in source_metadata],
        "stop_condition": "Stop when the answer is supported by successful query results.",
        "next_steps": [],
        "needs_clarification": False,
        "clarification_reason": "",
        "pending_follow_up": None,
    }


def _build_artifacts_and_citations(evidence: list[dict[str, Any]], agent: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    artifacts: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    for item in evidence:
        citation = {
            "citation_id": item["evidence_id"],
            "source": ", ".join(item.get("sources", [])),
            "title": item["title"],
            "summary": item["summary"],
        }
        citations.append(citation)
        artifacts.append(_artifact_from_evidence(item, citation["citation_id"], agent))
    return artifacts, citations


def _artifact_from_evidence(item: dict[str, Any], citation_id: str, agent: str) -> dict[str, Any]:
    rows = item.get("rows", [])
    columns = item.get("columns", [])
    answer_mode = item.get("answer_mode", "table")
    explicit_chart_type = _normalize_chart_type(item.get("chart_type"))
    numeric_columns = [col for col in columns if _column_is_numeric(rows, col)]
    if rows and answer_mode == "metric" and len(rows) == 1 and numeric_columns:
        value_col = numeric_columns[0]
        return {
            "kind": "metric",
            "title": item["title"],
            "value": rows[0].get(value_col),
            "subtitle": item["summary"],
            "citation_ids": [citation_id],
            "purpose": "supporting_evidence",
            "display_mode": "board_default",
            "source_role": agent,
            "confidence": "medium",
            "card_variant": "metric",
            "summary": item["summary"],
        }
    if rows and answer_mode == "table":
        return {
            "kind": "table",
            "title": item["title"],
            "columns": columns,
            "rows": rows,
            "citation_ids": [citation_id],
            "purpose": "supporting_evidence",
            "display_mode": "board_default",
            "source_role": agent,
            "confidence": "medium",
            "card_variant": "table",
            "summary": item["summary"],
        }
    if rows and len(columns) >= 2 and numeric_columns and (answer_mode == "chart" or len(rows) <= 30):
        label_column = next((col for col in columns if col not in numeric_columns), columns[0])
        value_columns = [col for col in numeric_columns if col != label_column]
        if not value_columns:
            value_columns = numeric_columns[:1]

        # Detect long-format data that should be pivoted into multi-series.
        # Pattern: exactly 3 columns — label, category (string), value (numeric).
        # Example: date | platform | order_count → pivot into one series per platform.
        non_numeric_non_label = [c for c in columns if c not in numeric_columns and c != label_column]
        if len(value_columns) == 1 and len(non_numeric_non_label) == 1:
            category_column = non_numeric_non_label[0]
            val_col = value_columns[0]
            categories = list(dict.fromkeys(str(row.get(category_column, "")) for row in rows))
            if 2 <= len(categories) <= 8:
                # Pivot: group by label, create one series per category
                from collections import OrderedDict
                label_order: list[str] = list(dict.fromkeys(str(row.get(label_column, "")) for row in rows))
                pivoted: dict[str, dict[str, float]] = OrderedDict()
                for lbl in label_order:
                    pivoted[lbl] = {cat: 0.0 for cat in categories}
                for row in rows:
                    lbl = str(row.get(label_column, ""))
                    cat = str(row.get(category_column, ""))
                    pivoted[lbl][cat] = float(row.get(val_col, 0) or 0)
                chart_type = _resolve_chart_type(
                    explicit_chart_type=explicit_chart_type,
                    rows=rows,
                    label_column=label_column,
                    value_columns=[val_col],
                )
                label_order = _normalize_week_labels(label_order)
                series = [
                    {"name": cat, "values": [pivoted[lbl][cat] for lbl in pivoted]}
                    for cat in categories
                ]
                from agent_router.downsample import downsample_chart
                label_order, series, _ds = downsample_chart(label_order, series)
                resolved_chart_type = chart_type
                dual_axis = False
                if resolved_chart_type == "dual_axis_line" or (resolved_chart_type == "line" and _detect_dual_axis(series)):
                    resolved_chart_type = "dual_axis_line"
                    dual_axis = True
                return {
                    "kind": "chart",
                    "title": item["title"],
                    "chart_type": resolved_chart_type,
                    "labels": label_order,
                    "series": series,
                    "multi_measure": False,
                    "dual_axis": dual_axis,
                    "citation_ids": [citation_id],
                    "purpose": "supporting_evidence",
                    "display_mode": "board_default",
                    "source_role": agent,
                    "confidence": "medium",
                    "card_variant": "chart",
                    "summary": item["summary"],
                }

        chart_type = _resolve_chart_type(
            explicit_chart_type=explicit_chart_type,
            rows=rows,
            label_column=label_column,
            value_columns=value_columns,
        )
        labels_list = _normalize_week_labels([str(row.get(label_column, "")) for row in rows])
        series = [
            {"name": col, "values": [float(row.get(col, 0) or 0) for row in rows]}
            for col in value_columns
        ]
        from agent_router.downsample import downsample_chart
        labels_list, series, _ds = downsample_chart(labels_list, series)
        dual_axis = False
        if chart_type == "dual_axis_line" or (chart_type == "line" and _detect_dual_axis(series)):
            chart_type = "dual_axis_line"
            dual_axis = True
        return {
            "kind": "chart",
            "title": item["title"],
            "chart_type": chart_type,
            "labels": labels_list,
            "series": series,
            "multi_measure": len(value_columns) > 1,
            "dual_axis": dual_axis,
            "citation_ids": [citation_id],
            "purpose": "supporting_evidence",
            "display_mode": "board_default",
            "source_role": agent,
            "confidence": "medium",
            "card_variant": "chart",
            "summary": item["summary"],
        }
    return {
        "kind": "table",
        "title": item["title"],
        "columns": columns,
        "rows": rows,
        "citation_ids": [citation_id],
        "purpose": "supporting_evidence",
        "display_mode": "board_default",
        "source_role": agent,
        "confidence": "medium",
        "card_variant": "table",
        "summary": item["summary"],
    }


def _structured_evidence_response(query: str, evidence: list[dict[str, Any]]) -> str | None:
    if len(evidence) != 1:
        return None
    item = evidence[0]
    if item.get("answer_mode") != "table":
        return None
    rows = item.get("rows") or []
    columns = item.get("columns") or []
    if not rows or not columns or len(rows) > 12:
        return None

    title = str(item.get("title") or "Result").strip()
    lines = [f"{title} from `{', '.join(item.get('sources', []))}`:"]
    lines.append("")
    lines.append(_markdown_table(columns, rows))
    return "\n".join(lines)


def _markdown_table(columns: list[str], rows: list[dict[str, Any]]) -> str:
    headers = [str(column) for column in columns]
    header_line = "| " + " | ".join(headers) + " |"
    divider_line = "| " + " | ".join("---" for _ in headers) + " |"
    body_lines = []
    for row in rows:
        values = [_markdown_cell(row.get(column)) for column in columns]
        body_lines.append("| " + " | ".join(values) + " |")
    return "\n".join([header_line, divider_line, *body_lines])


def _markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            value = int(value)
        else:
            value = round(value, 2)
    return str(value).replace("|", "\\|")


def _default_next_steps(role: dict[str, Any]) -> list[str]:
    skills = role.get("skills", [])
    if len(skills) >= 2:
        return [f"Ask for a deeper cut on {skills[0].lower()}.", f"Ask for a follow-up using {skills[1].lower()}."]
    return ["Ask a follow-up question to narrow the evidence."]


def _document_rows(content: str, terms: list[str], query: str) -> list[dict[str, str]]:
    search_terms = [str(term).strip() for term in terms if str(term).strip()]
    rows: list[dict[str, str]] = []
    lowered = content.lower()
    for term in search_terms[:3]:
        idx = lowered.find(term.lower())
        if idx == -1:
            continue
        start = max(0, idx - 120)
        end = min(len(content), idx + 240)
        rows.append({"term": term, "excerpt": content[start:end].replace("\n", " ").strip()})
    if not rows:
        rows.append({"term": "preview", "excerpt": content[:280].replace("\n", " ").strip()})
    return rows[:MAX_TABLE_RESULT_ROWS]


def _summarize_attempt(record: dict[str, Any]) -> str:
    rows = record.get("rows", [])
    sources = ", ".join(record.get("sources", []))
    title = record.get("title") or "Result"
    if record.get("kind") == "document":
        return f"{title} surfaced {len(rows)} excerpt(s) from {sources}."
    if len(rows) == 1:
        preview = ", ".join(f"{key}={value}" for key, value in list(rows[0].items())[:3])
        return f"{title} returned 1 row from {sources}: {preview}."
    return f"{title} returned {len(rows)} rows from {sources}."


def _normalize_week_labels(labels: list[str]) -> list[str]:
    """Convert week-number labels (e.g. '2024-40') to week-start dates (e.g. '2024-09-30').

    Handles both ISO weeks (1-53) and strftime %W weeks (0-53).
    Also handles 'YYYY-WNN' format.  Leaves non-week labels unchanged.
    """
    import re
    from datetime import date, timedelta, datetime

    normalized: list[str] = []
    for label in labels:
        # Match "2024-40" or "2024-W40" patterns
        m = re.match(r"^(\d{4})-W?(\d{1,2})$", label)
        if m:
            year, week = int(m.group(1)), int(m.group(2))
            # Try ISO week first (1-53)
            if 1 <= week <= 53:
                try:
                    d = date.fromisocalendar(year, week, 1)
                    normalized.append(d.isoformat())
                    continue
                except ValueError:
                    pass
            # Fall back to strftime %W style (0-53, Monday-based)
            if 0 <= week <= 53:
                try:
                    # %W: week 0 = days before first Monday, week 1 = first Monday
                    d = datetime.strptime(f"{year}-W{week:02d}-1", "%Y-W%W-%w").date()
                    if d.weekday() != 0:  # ensure Monday
                        d = d - timedelta(days=d.weekday())
                    normalized.append(d.isoformat())
                    continue
                except ValueError:
                    pass
        normalized.append(label)
    return normalized


_VALID_CHART_TYPES = {"bar", "line", "funnel", "pie", "scatter", "heatmap", "histogram", "box", "dual_axis_line"}


def _normalize_chart_type(value: Any) -> str | None:
    chart_type = str(value or "").strip().lower()
    if chart_type in _VALID_CHART_TYPES:
        return chart_type
    return None


def _resolve_chart_type(
    explicit_chart_type: str | None,
    rows: list[dict[str, Any]],
    label_column: str,
    value_columns: list[str],
) -> str:
    inferred = "line" if _looks_like_time_column(rows, label_column) else "bar"
    if explicit_chart_type == "funnel":
        if len(value_columns) == 1 and len(rows) >= 2:
            return "funnel"
        return inferred
    if explicit_chart_type == "pie":
        if len(value_columns) == 1 and 2 <= len(rows) <= 8:
            return "pie"
        return inferred
    if explicit_chart_type == "scatter":
        if len(value_columns) >= 2:
            return "scatter"
        return inferred
    if explicit_chart_type in {"heatmap", "histogram", "box"}:
        return explicit_chart_type
    if explicit_chart_type == "dual_axis_line":
        if len(value_columns) >= 2:
            return "dual_axis_line"
        return "line"
    if explicit_chart_type in {"bar", "line"}:
        return explicit_chart_type
    return inferred


def _detect_dual_axis(series: list[dict[str, Any]]) -> bool:
    """Return True when two series have values differing by more than 10x in magnitude."""
    if len(series) != 2:
        return False
    def _max_abs(values: list) -> float:
        nums = [abs(v) for v in values if isinstance(v, (int, float)) and v is not None]
        return max(nums) if nums else 0.0
    mag_a = _max_abs(series[0].get("values", []))
    mag_b = _max_abs(series[1].get("values", []))
    if mag_a == 0 or mag_b == 0:
        return False
    ratio = max(mag_a, mag_b) / min(mag_a, mag_b)
    return ratio >= 10


def _looks_like_time_column(rows: list[dict[str, Any]], column: str) -> bool:
    values = [str(row.get(column, "")) for row in rows[:3]]
    return all(any(char.isdigit() for char in value) and ("-" in value or ":" in value) for value in values if value)


def _column_is_numeric(rows: list[dict[str, Any]], column: str) -> bool:
    if not rows:
        return False
    seen = False
    for row in rows[:5]:
        value = row.get(column)
        if value is None or value == "":
            continue
        seen = True
        if not isinstance(value, (int, float)):
            return False
    return seen


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _normalize_pending_follow_up(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    prompt = str(value.get("prompt") or "").strip()
    raw_choices = value.get("choices") or []
    choices = [str(choice).strip() for choice in raw_choices if str(choice).strip()][:3]
    if not prompt:
        return None
    default_choice = str(value.get("default_choice") or (choices[0] if choices else "")).strip()
    if choices and default_choice not in choices:
        default_choice = choices[0]
    resolved_query_template = str(value.get("resolved_query_template") or "{original_question}\nClarification: {choice}").strip()
    return {
        "prompt": prompt,
        "choices": choices,
        "default_choice": default_choice,
        "resolved_query_template": resolved_query_template,
        "allow_free_text": bool(value.get("allow_free_text", True)),
    }


def _last_same_agent_history_item(history: list[dict[str, Any]], agent: str) -> dict[str, Any] | None:
    for item in reversed(history):
        if item.get("agent") == agent:
            return item
    return None


def _clarification_state(history: list[dict[str, Any]], agent: str) -> dict[str, Any]:
    last_item = _last_same_agent_history_item(history, agent)
    planner = (last_item or {}).get("planner") or {}
    clarification_history = planner.get("clarification_history") or []
    if not isinstance(clarification_history, list):
        clarification_history = []
    clarification_count = int(planner.get("clarification_count") or 0)
    pending_follow_up = _normalize_pending_follow_up(planner.get("pending_follow_up"))
    original_question = str(planner.get("original_query") or (last_item or {}).get("query") or "").strip()
    effective_query = str(planner.get("effective_query") or (last_item or {}).get("query") or "").strip()
    return {
        "clarification_count": clarification_count,
        "clarification_history": clarification_history,
        "pending_follow_up": pending_follow_up,
        "original_query": original_question,
        "effective_query": effective_query,
        "last_item": last_item,
    }


def _resolve_clarification_reply(query: str, clarification_state: dict[str, Any]) -> dict[str, Any]:
    pending = clarification_state.get("pending_follow_up")
    original_query = clarification_state.get("original_query") or query
    clarification_history = list(clarification_state.get("clarification_history") or [])
    if not pending:
        return {
            "original_query": query,
            "effective_query": query,
            "clarification_history": clarification_history,
            "note": None,
            "latest_reply": None,
        }

    reply = query.strip()
    matched_choice = _match_pending_choice(reply, pending.get("choices", []))
    chosen_value = matched_choice or reply
    effective_query = _render_resolved_query(
        pending.get("resolved_query_template") or "{original_question}\nClarification: {choice}",
        original_query,
        chosen_value,
    )
    mode = "choice" if matched_choice else "free_text"
    clarification_history.append(
        {
            "prompt": pending.get("prompt"),
            "answer": chosen_value,
            "mode": mode,
            "resolved_query": effective_query,
        }
    )
    note = "Resolved the user's reply against the agent's clarifying question."
    if not matched_choice:
        note = "Used the user's free-text clarification to continue the investigation."
    return {
        "original_query": original_query,
        "effective_query": effective_query,
        "clarification_history": clarification_history,
        "note": note,
        "latest_reply": reply,
    }


def _match_pending_choice(reply: str, choices: list[str]) -> str | None:
    normalized_reply = _normalize_text(reply)
    if not normalized_reply:
        return None
    exact = next((choice for choice in choices if _normalize_text(choice) == normalized_reply), None)
    if exact:
        return exact
    partial_matches = [choice for choice in choices if normalized_reply in _normalize_text(choice)]
    if len(partial_matches) == 1:
        return partial_matches[0]
    return None


def _render_resolved_query(template: str, original_query: str, choice: str) -> str:
    try:
        return template.format(choice=choice, original_question=original_query)
    except Exception:
        return f"{original_query}\nClarification: {choice}"


def _finalize_plan_clarification_state(
    plan: dict[str, Any],
    original_query: str,
    effective_query: str,
    prior_clarification_count: int,
    clarification_history: list[dict[str, Any]],
) -> dict[str, Any]:
    pending_follow_up = plan.get("pending_follow_up")
    clarification_count = prior_clarification_count + (1 if pending_follow_up else 0)
    return {
        **plan,
        "original_query": original_query,
        "effective_query": effective_query,
        "clarification_count": clarification_count,
        "clarification_history": clarification_history,
    }


def _clarification_cap_warning(plan: dict[str, Any], prior_clarification_count: int) -> str | None:
    if not plan.get("pending_follow_up"):
        return None
    if prior_clarification_count >= MAX_CLARIFICATION_QUESTIONS:
        return "Clarification limit reached, so the agent proceeded without asking another question."
    return None


def _clarification_response(plan: dict[str, Any]) -> str:
    pending = plan.get("pending_follow_up") or {}
    reason = str(plan.get("clarification_reason") or "").strip()
    parts = []
    if reason:
        parts.append(reason)
    parts.append(str(pending.get("prompt") or "").strip())
    choices = pending.get("choices") or []
    if choices:
        parts.append("\n".join(f"- {choice}" for choice in choices))
    return "\n\n".join(part for part in parts if part).strip()


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def _chat_json(
    llm: LLMClient,
    system: str,
    payload: dict[str, Any],
    normalize: Any,
    purpose: str,
) -> tuple[dict[str, Any] | None, str | None]:
    latest_error: str | None = None
    current_payload = dict(payload)
    for attempt in range(2):
        try:
            value = llm.chat(system=system, user=json.dumps(current_payload, ensure_ascii=True))
            if not isinstance(value, dict):
                raise ValueError(f"{purpose} did not return a JSON object.")
            return normalize(value), None
        except Exception as exc:
            latest_error = str(exc)
            logger.warning("%s attempt %s failed: %s", purpose.title(), attempt + 1, exc)
            current_payload = {
                **payload,
                "previous_error": latest_error,
                "instruction": "Return a valid JSON object that matches the response schema.",
            }
    return None, latest_error
