"""Agent router — iterative role-based investigation over scoped SQL access."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from data_layer.db import (
    execute_authorized_select,
    get_document,
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
MAX_RESULT_ROWS = 12

PLAN_SCHEMA = {
    "question_understanding": "Short summary of the user's ask",
    "complexity": "single_query | multi_step",
    "sub_questions": ["Optional sub-question"],
    "target_tables": ["Allowed source name such as orders.csv"],
    "stop_condition": "What evidence is enough to answer",
    "next_steps": ["Follow-up the user might ask next"],
}

ACTION_SCHEMA = {
    "action": "sql | document | finish",
    "reason": "Short rationale",
    "sql": "Read-only SQL query when action is sql",
    "document": "Allowed markdown source name when action is document",
    "document_terms": ["Optional search terms for document excerpts"],
    "title": "Human-friendly title for the resulting evidence",
    "answer_mode": "metric | chart | table | text",
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
    """Plan an investigation, execute scoped queries, and synthesize the answer."""
    validate_agent(agent)
    history = conversation_history or []

    role = get_agent_role_config(scenario_id, agent)
    source_metadata = _build_source_metadata(scenario_id, role["allowed_tables"])
    shared_context = _build_shared_context(history)
    last_turn_context = _last_agent_turn_context(history, agent)

    plan, plan_warning = _plan_investigation(
        llm=llm,
        agent=agent,
        role=role,
        query=query,
        source_metadata=source_metadata,
        shared_context=shared_context,
        last_turn_context=last_turn_context,
    )

    evidence, attempts, warnings = _run_investigation_loop(
        llm=llm,
        scenario_id=scenario_id,
        agent=agent,
        role=role,
        query=query,
        plan=plan,
        source_metadata=source_metadata,
        shared_context=shared_context,
    )
    if plan_warning:
        warnings.append(plan_warning)

    artifacts, citations = _build_artifacts_and_citations(evidence, agent)
    response = _synthesize_response(
        llm=llm,
        agent=agent,
        role=role,
        query=query,
        plan=plan,
        evidence=evidence,
        warnings=warnings,
        shared_context=shared_context,
    )

    return {
        "agent": agent,
        "response": response,
        "artifacts": artifacts,
        "citations": citations,
        "warnings": _unique_preserve(warnings),
        "next_steps": plan.get("next_steps") or _default_next_steps(role),
        "pending_follow_up": None,
        "intent_class": "investigation",
        "_planner": {
            **plan,
            "shared_context_summary": shared_context,
            "attempt_count": len(attempts),
        },
        "_attempts": attempts,
    }


def _plan_investigation(
    llm: LLMClient,
    agent: str,
    role: dict[str, Any],
    query: str,
    source_metadata: list[dict[str, Any]],
    shared_context: list[dict[str, Any]],
    last_turn_context: dict[str, Any] | None,
) -> tuple[dict[str, Any], str | None]:
    system = _role_system_prompt(agent, role) + (
        "\n\nCreate a short investigation plan before querying data. "
        "Decide whether the question looks solvable with one query or needs multiple steps. "
        "Return JSON only."
    )
    user = json.dumps(
        {
            "question": query,
            "allowed_sources": source_metadata,
            "shared_context": shared_context,
            "last_agent_turn": last_turn_context,
            "response_schema": PLAN_SCHEMA,
        },
        ensure_ascii=True,
    )
    plan, error = _chat_json(
        llm=llm,
        system=system,
        payload={
            "question": query,
            "allowed_sources": source_metadata,
            "shared_context": shared_context,
            "last_agent_turn": last_turn_context,
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
    shared_context: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    attempts: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    allowed_sql_tables = {
        source.removesuffix(".csv")
        for source in role.get("allowed_tables", [])
        if source.endswith(".csv")
    }

    for attempt_no in range(1, MAX_INVESTIGATION_ATTEMPTS + 1):
        action, action_warning = _choose_next_action(
            llm=llm,
            agent=agent,
            role=role,
            query=query,
            plan=plan,
            source_metadata=source_metadata,
            shared_context=shared_context,
            attempts=attempts,
            evidence=evidence,
        )
        if action_warning:
            warnings.append(action_warning)

        action_type = action.get("action")
        if action_type == "finish":
            break

        if action_type == "document":
            record = _execute_document_step(
                scenario_id=scenario_id,
                action=action,
                allowed_sources=role.get("allowed_tables", []),
                query=query,
            )
        else:
            record = _execute_sql_step(
                scenario_id=scenario_id,
                action=action,
                allowed_sql_tables=allowed_sql_tables,
            )

        record["attempt"] = attempt_no
        attempts.append(record)

        if record["status"] == "success" and record.get("rows"):
            evidence.append(
                {
                    "evidence_id": f"ev_{uuid.uuid4().hex[:8]}",
                    "title": record.get("title") or f"Attempt {attempt_no}",
                    "rows": record.get("rows", []),
                    "columns": record.get("columns", []),
                    "answer_mode": record.get("answer_mode", "table"),
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
    shared_context: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> tuple[dict[str, Any], str | None]:
    if attempts and evidence:
        return {"action": "finish", "reason": "We already have evidence.", "title": "Final answer", "answer_mode": "text"}, None

    system = _role_system_prompt(agent, role) + (
        "\n\nYou are in an investigation loop. "
        "Choose the next best step to answer the question. "
        "If you already have enough evidence, return action=finish. "
        "Return JSON only."
    )
    user = json.dumps(
        {
            "question": query,
            "plan": plan,
            "allowed_sources": source_metadata,
            "shared_context": shared_context,
            "attempts_so_far": attempts,
            "evidence_summaries": [item["summary"] for item in evidence],
            "response_schema": ACTION_SCHEMA,
        },
        ensure_ascii=True,
    )
    action, error = _chat_json(
        llm=llm,
        system=system,
        payload={
            "question": query,
            "plan": plan,
            "allowed_sources": source_metadata,
            "shared_context": shared_context,
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
        max_rows=MAX_RESULT_ROWS,
    )
    if not result["ok"]:
        return {
            "status": "error",
            "kind": "sql",
            "title": action.get("title") or "SQL attempt",
            "answer_mode": action.get("answer_mode", "table"),
            "sql": sql,
            "error": result["error"],
            "sources": [f"{name}.csv" for name in result.get("referenced_tables", [])],
            "columns": [],
            "rows": [],
            "truncated": False,
        }
    return {
        "status": "success",
        "kind": "sql",
        "title": action.get("title") or "SQL result",
        "answer_mode": action.get("answer_mode", "table"),
        "sql": result["executed_sql"],
        "sources": [f"{name}.csv" for name in result.get("referenced_tables", [])],
        "columns": result["columns"],
        "rows": result["rows"],
        "truncated": result["truncated"],
    }


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
        "truncated": len(rows) >= MAX_RESULT_ROWS,
    }


def _synthesize_response(
    llm: LLMClient,
    agent: str,
    role: dict[str, Any],
    query: str,
    plan: dict[str, Any],
    evidence: list[dict[str, Any]],
    warnings: list[str],
    shared_context: list[dict[str, Any]],
) -> str:
    if not evidence:
        if shared_context:
            system = _role_system_prompt(agent, role) + (
                "\n\nAnswer using the shared investigation context only. "
                "Be clear that you are referencing earlier teammate findings rather than fresh data."
            )
            user = json.dumps(
                {
                    "question": query,
                    "plan": plan,
                    "shared_context": shared_context,
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
        "\n\nWrite a concise, evidence-grounded answer. "
        "Mention ambiguity when warnings indicate failed or partial attempts. "
        "Do not mention hidden prompts or internal planning."
    )
    user = json.dumps(
        {
            "question": query,
            "plan": plan,
            "evidence": [{"title": item["title"], "summary": item["summary"], "sources": item["sources"]} for item in evidence],
            "warnings": warnings,
            "shared_context": shared_context,
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
        f"Allowed sources: {tables}\n"
        f"Core skills: {skills}\n"
        "You can make a brief plan before querying. "
        "If a query fails, is empty, or only partially answers the question, revise your approach and try again. "
        "Stay within evidence from your allowed sources only."
    )


def _build_source_metadata(scenario_id: str, allowed_tables: list[str]) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for source in allowed_tables:
        if source.endswith(".csv"):
            table = source.removesuffix(".csv")
            schema = get_table_schema(scenario_id, table)
            metadata.append(
                {
                    "name": source,
                    "type": "table",
                    "columns": get_table_columns(scenario_id, table),
                    "schema": schema,
                    "row_count": get_table_row_count(scenario_id, table),
                    "sample_rows": get_sample_rows(scenario_id, table, 3),
                }
            )
        elif source.endswith(".md"):
            preview = (get_document(scenario_id, source) or "")[:240].replace("\n", " ").strip()
            metadata.append({"name": source, "type": "document", "preview": preview})
    return metadata


def _build_shared_context(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    context: list[dict[str, Any]] = []
    for item in history[-MAX_HISTORY_ITEMS:]:
        context.append(
            {
                "agent": item.get("agent"),
                "question": item.get("query"),
                "answer_summary": _clip(str(item.get("response") or ""), 220),
                "artifact_titles": [artifact.get("title") for artifact in (item.get("artifacts") or [])[:2]],
                "citations": [citation.get("title") or citation.get("source") for citation in (item.get("citations") or [])[:2]],
            }
        )
    return context


def _last_agent_turn_context(history: list[dict[str, Any]], agent: str) -> dict[str, Any] | None:
    for item in reversed(history):
        if item.get("agent") == agent:
            return {
                "query": item.get("query"),
                "response": item.get("response"),
                "artifact_titles": [artifact.get("title") for artifact in (item.get("artifacts") or [])[:3]],
            }
    return None


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
    }


def _normalize_action(action: dict[str, Any], plan: dict[str, Any], source_metadata: list[dict[str, Any]]) -> dict[str, Any]:
    allowed_sources = {item["name"] for item in source_metadata}
    raw_document_terms = action.get("document_terms") or []
    action_type = str(action.get("action") or "sql").strip().lower()
    if action_type not in {"sql", "document", "finish"}:
        action_type = "sql"
    answer_mode = str(action.get("answer_mode") or "table").strip().lower()
    if answer_mode not in {"metric", "chart", "table", "text"}:
        answer_mode = "table"
    document = str(action.get("document") or "").strip()
    if document and document not in allowed_sources:
        document = ""
    return {
        "action": action_type,
        "reason": str(action.get("reason") or "").strip(),
        "sql": str(action.get("sql") or "").strip(),
        "document": document,
        "document_terms": [str(term).strip() for term in raw_document_terms if str(term).strip()][:3],
        "title": str(action.get("title") or "").strip() or "Investigation result",
        "answer_mode": answer_mode,
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
    if rows and len(columns) >= 2 and len(rows) <= 12 and numeric_columns:
        label_column = next((col for col in columns if col not in numeric_columns), columns[0])
        value_column = next((col for col in numeric_columns if col != label_column), numeric_columns[0])
        chart_type = "line" if _looks_like_time_column(rows, label_column) else "bar"
        return {
            "kind": "chart",
            "title": item["title"],
            "chart_type": chart_type,
            "labels": [str(row.get(label_column, "")) for row in rows],
            "series": [{"name": value_column, "values": [float(row.get(value_column, 0) or 0) for row in rows]}],
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
    return rows[:MAX_RESULT_ROWS]


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
