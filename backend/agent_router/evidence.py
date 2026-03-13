"""Deterministic evidence execution and artifact building."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from data_layer.db import (
    build_where_clause,
    get_document,
    get_table_columns,
    get_table_row_count,
    query,
    query_value,
)
from scenario_loader.loader import get_agent_capability_profile, get_agent_data_access, load_reference

DEFAULT_LIMIT = 8
MAX_LIMIT = 25

FUNNEL_STEP_ORDER = [
    "app_open",
    "restaurant_view",
    "add_to_cart",
    "checkout_start",
    "payment_attempt",
    "order_complete",
]


def get_agent_source_metadata(scenario_id: str, agent: str) -> list[dict[str, Any]]:
    access = get_agent_data_access(scenario_id, agent)
    reference = load_reference(scenario_id)
    source_lookup = {}
    for domain in reference.get("source_catalog", []):
        for source in domain.get("sources", []):
            source_lookup[source["name"]] = source

    sources = []
    for source_name in access.get("tables", []):
        info: dict[str, Any] = {
            "name": source_name,
            "description": source_lookup.get(source_name, {}).get("description", ""),
            "fields": source_lookup.get(source_name, {}).get("fields", []),
        }
        if source_name.endswith(".csv"):
            table = source_name.removesuffix(".csv")
            info["type"] = "csv"
            info["columns"] = get_table_columns(scenario_id, table)
            info["date_column"] = _first_date_column(info["columns"])
        elif source_name.endswith(".md"):
            info["type"] = "md"
        else:
            info["type"] = "unknown"
        sources.append(info)
    return sources


def execute_operations(
    scenario_id: str,
    agent: str,
    operations: list[dict[str, Any]],
    query_text: str,
    answer_mode: str,
    intent_class: str,
    capability_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allowed_sources = set(get_agent_data_access(scenario_id, agent).get("tables", []))
    capability_profile = capability_profile or get_agent_capability_profile(scenario_id, agent)
    evidence: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    warnings: list[str] = []
    alias_results: dict[str, dict[str, Any]] = {}

    for index, raw_operation in enumerate(operations, start=1):
        operation = _resolve_templates(raw_operation, alias_results)
        op_type = operation.get("type", "")
        source = operation.get("source") or operation.get("filename")

        if source and source not in allowed_sources:
            warnings.append(f"Skipped unauthorized source '{source}' for {agent}.")
            continue

        if op_type == "lookup_rows":
            result = _lookup_rows(scenario_id, operation)
        elif op_type == "rank_rows":
            result = _rank_rows(scenario_id, operation)
        elif op_type == "aggregate_breakdown":
            result = _aggregate_breakdown(scenario_id, operation)
        elif op_type == "aggregate_timeseries":
            result = _aggregate_timeseries(scenario_id, operation)
        elif op_type == "compute_funnel":
            result = _compute_funnel(scenario_id, operation)
        elif op_type == "read_document_excerpt":
            result = _read_document_excerpt(scenario_id, operation, query_text)
        elif op_type == "summarize_source_profile":
            result = _summarize_source_profile(scenario_id, operation)
        elif op_type == "summarize_date_span":
            result = _summarize_date_span(scenario_id, operation)
        elif op_type == "compare_segments":
            result = _compare_segments(scenario_id, operation)
        elif op_type == "summarize_metric_delta":
            result = _summarize_metric_delta(scenario_id, operation)
        elif op_type == "extract_feedback_themes":
            result = _extract_feedback_themes(scenario_id, operation)
        elif op_type == "select_representative_quotes":
            result = _select_representative_quotes(scenario_id, operation, query_text)
        elif op_type == "count_issue_mentions":
            result = _count_issue_mentions(scenario_id, operation)
        elif op_type == "summarize_ux_change_impact":
            result = _summarize_ux_change_impact(scenario_id, operation)
        elif op_type == "build_incident_timeline":
            result = _build_incident_timeline(scenario_id, operation)
        elif op_type == "correlate_deployments_with_metrics":
            result = _correlate_deployments_with_metrics(scenario_id, operation)
        elif op_type == "summarize_error_shift":
            result = _summarize_error_shift(scenario_id, operation)
        elif op_type == "compare_pre_post_rollout":
            result = _compare_pre_post_rollout(scenario_id, operation)
        else:
            warnings.append(f"Skipped unsupported operation '{op_type}'.")
            continue

        result["operation"] = op_type
        result["source"] = source or ""
        result["evidence_id"] = result.get("evidence_id") or f"ev_{uuid.uuid4().hex[:8]}"
        result["warnings"] = result.get("warnings", [])
        title, title_warning = _resolve_result_title(op_type, operation, result, query_text)
        result["title"] = title
        if title_warning:
            result["warnings"].append(title_warning)
        evidence.append(result)
        warnings.extend(result["warnings"])
        citations.append({
            "citation_id": result["evidence_id"],
            "source": result["source"],
            "title": result["title"],
            "summary": result.get("summary", ""),
        })
        alias = operation.get("alias")
        if alias:
            alias_results[alias] = result

    artifacts = build_artifacts(evidence, answer_mode, query_text, agent, intent_class, capability_profile)
    artifacts, validation_warnings = validate_artifacts(artifacts, citations, query_text)
    warnings.extend(validation_warnings)

    return {
        "evidence": evidence,
        "citations": citations,
        "warnings": _unique_preserve(warnings),
        "artifacts": artifacts,
    }


def summarize_evidence(history: list[dict[str, Any]], agent: str, limit: int = 4) -> list[str]:
    summaries: list[str] = []
    for item in history:
        if item.get("agent") != agent:
            continue
        for citation in item.get("citations", [])[:2]:
            title = citation.get("title") or citation.get("source") or "Evidence"
            summary = citation.get("summary") or ""
            summaries.append(f"{title}: {summary}".strip(": "))
    return summaries[-limit:]


def build_artifacts(
    evidence: list[dict[str, Any]],
    answer_mode: str,
    query_text: str,
    agent: str,
    intent_class: str,
    capability_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for item in evidence:
        citation_ids = [item["evidence_id"]]
        op_type = item.get("operation")
        title = item.get("title") or query_text
        metadata = _artifact_metadata(item, agent, intent_class, capability_profile, query_text)

        if op_type in {"lookup_rows", "read_document_excerpt"}:
            rows = item.get("rows", [])
            columns = item.get("columns", [])
            if rows:
                artifacts.append({
                    "kind": "table",
                    "title": title,
                    "columns": columns,
                    "rows": rows,
                    "citation_ids": citation_ids,
                    **metadata,
                })
            continue

        if op_type == "aggregate_timeseries":
            artifacts.append({
                "kind": "chart",
                "title": title,
                "chart_type": "line",
                "labels": item.get("labels", []),
                "series": item.get("series", []),
                "unit": item.get("unit"),
                "citation_ids": citation_ids,
                **metadata,
            })
            continue

        if op_type == "compute_funnel":
            artifacts.append({
                "kind": "chart",
                "title": title,
                "chart_type": "funnel",
                "labels": item.get("labels", []),
                "series": item.get("series", []),
                "unit": item.get("unit"),
                "citation_ids": citation_ids,
                **metadata,
            })
            continue

        rows = item.get("rows", [])
        columns = item.get("columns", [])
        value_column = item.get("value_column")
        if answer_mode == "metric" and rows and value_column and len(rows) == 1:
            row = rows[0]
            artifacts.append({
                "kind": "metric",
                "title": title,
                "value": row.get(value_column),
                "unit": item.get("unit"),
                "subtitle": item.get("summary"),
                "citation_ids": citation_ids,
                **metadata,
            })
        elif rows and value_column and item.get("group_by"):
            artifacts.append({
                "kind": "chart",
                "title": title,
                "chart_type": "bar",
                "labels": [str(row.get(item["group_by"], "")) for row in rows],
                "series": [{
                    "name": value_column,
                    "values": [float(row.get(value_column, 0) or 0) for row in rows],
                }],
                "unit": item.get("unit"),
                "citation_ids": citation_ids,
                **metadata,
            })
        elif rows:
            artifacts.append({
                "kind": "table",
                "title": title,
                "columns": columns,
                "rows": rows,
                "citation_ids": citation_ids,
                **metadata,
            })
    return artifacts


def validate_artifacts(
    artifacts: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    query_text: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    citation_ids = {citation["citation_id"] for citation in citations}
    valid: list[dict[str, Any]] = []
    warnings: list[str] = []

    for artifact in artifacts:
        kind = artifact.get("kind")
        refs = artifact.get("citation_ids")
        if not refs or not all(ref in citation_ids for ref in refs):
            warnings.append(f"Dropped artifact '{artifact.get('title', 'Untitled')}' due to missing citations.")
            continue

        if kind == "metric":
            if "value" not in artifact:
                warnings.append(f"Dropped metric artifact '{artifact.get('title', 'Untitled')}' due to missing value.")
                continue
        elif kind == "chart":
            labels = artifact.get("labels")
            series = artifact.get("series")
            if not isinstance(labels, list) or not isinstance(series, list) or not labels:
                warnings.append(f"Dropped chart artifact '{artifact.get('title', 'Untitled')}' due to malformed series.")
                continue
            if any(len(item.get("values", [])) != len(labels) for item in series):
                warnings.append(f"Dropped chart artifact '{artifact.get('title', 'Untitled')}' due to length mismatch.")
                continue
        elif kind == "table":
            columns = artifact.get("columns")
            rows = artifact.get("rows")
            if not isinstance(columns, list) or not isinstance(rows, list):
                warnings.append(f"Dropped table artifact '{artifact.get('title', 'Untitled')}' due to malformed rows.")
                continue
        else:
            warnings.append(f"Dropped unsupported artifact kind '{kind}'.")
            continue

        artifact.setdefault("purpose", "supporting_evidence")
        artifact.setdefault("display_mode", "board_default")
        artifact.setdefault("summary", artifact.get("subtitle") or artifact.get("title") or query_text)
        artifact.setdefault("source_role", "analyst")
        artifact.setdefault("confidence", "medium")
        artifact.setdefault("card_variant", _default_card_variant(artifact))
        if artifact["display_mode"] not in {"inline_only", "board_optional", "board_default"}:
            warnings.append(f"Dropped artifact '{artifact.get('title', 'Untitled')}' due to invalid display_mode.")
            continue
        if artifact["purpose"] not in {"reference", "scratch", "supporting_evidence", "final_evidence"}:
            warnings.append(f"Dropped artifact '{artifact.get('title', 'Untitled')}' due to invalid purpose.")
            continue
        if artifact["confidence"] not in {"low", "medium", "high"}:
            warnings.append(f"Dropped artifact '{artifact.get('title', 'Untitled')}' due to invalid confidence.")
            continue

        if artifact["display_mode"] != "inline_only" and not _artifact_supports_board(artifact):
            warnings.append(f"Suppressed low-value artifact '{artifact.get('title', 'Untitled')}' from the evidence board.")
            artifact["display_mode"] = "inline_only"
            artifact["purpose"] = "reference" if artifact["purpose"] == "scratch" else artifact["purpose"]

        valid.append(artifact)

    return valid, warnings


# ────────────────────────────────────────────────────
# Evidence operations (SQLite-backed)
# ────────────────────────────────────────────────────


def _table_name(source: str) -> str:
    """Convert source filename to SQLite table name: 'orders.csv' → 'orders'."""
    if source.endswith(".csv"):
        return source.removesuffix(".csv")
    return source


def _resolve_column(name: str | None, all_columns: list[str]) -> str | None:
    """Resolve a column name with case-insensitive fallback."""
    if not name:
        return None
    if name in all_columns:
        return name
    lower_map = {col.lower(): col for col in all_columns}
    return lower_map.get(name.lower())


def _lookup_rows(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    table = _table_name(operation["source"])
    all_columns = get_table_columns(scenario_id, table)
    where, params = build_where_clause(operation.get("filters"), all_columns)

    columns = _validate_columns(operation.get("columns"), all_columns)
    select_cols = ", ".join(f"[{c}]" for c in columns) if columns else "*"
    if not columns:
        columns = all_columns

    sort_by = operation.get("sort_by")
    sort_order = operation.get("sort_order", "asc")
    order_clause = ""
    if sort_by and sort_by in all_columns:
        order_clause = f"ORDER BY [{sort_by}] {'ASC' if sort_order == 'asc' else 'DESC'}"

    limit = _normalized_limit(operation.get("limit"))
    warnings: list[str] = []

    # Check for ties when limit=1 with sorting
    if sort_by and limit == 1 and sort_by in all_columns:
        sql = f"SELECT {select_cols} FROM [{table}] {where} {order_clause}"
        all_rows = query(scenario_id, sql, params)
        if all_rows:
            top_value = all_rows[0].get(sort_by)
            tied = [r for r in all_rows if r.get(sort_by) == top_value]
            if len(tied) > 1:
                warnings.append(
                    f"'{operation.get('title') or 'Requested result'}' is ambiguous because {len(tied)} rows share the same {sort_by} value."
                )
                rows = tied[:MAX_LIMIT]
            else:
                rows = all_rows[:1]
        else:
            rows = []
    else:
        sql = f"SELECT {select_cols} FROM [{table}] {where} {order_clause} LIMIT ?"
        rows = query(scenario_id, sql, params + [limit])

    summary = f"Found {len(rows)} matching row(s) in {operation['source']}."
    return {
        "columns": columns,
        "rows": rows,
        "summary": summary,
        "warnings": warnings,
    }


def _rank_rows(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    table = _table_name(operation["source"])
    all_columns = get_table_columns(scenario_id, table)
    where, params = build_where_clause(operation.get("filters"), all_columns)

    group_by = _resolve_column(operation.get("group_by"), all_columns)
    if not group_by:
        return {
            "columns": [],
            "rows": [],
            "summary": f"Could not rank rows for {operation['source']} because group_by is missing or invalid.",
            "warnings": [f"Operation '{operation.get('title') or 'rank_rows'}' is missing a valid group_by column."],
        }

    metric = operation.get("metric")
    agg = operation.get("agg", "count")
    if metric and metric in all_columns and agg != "count":
        value_column = f"{metric}_{agg}"
        select_expr = f"[{group_by}], {_sql_agg(agg, metric)} AS [{value_column}]"
    else:
        value_column = "count"
        select_expr = f"[{group_by}], COUNT(*) AS [count]"

    sort_by = operation.get("sort_by") or value_column
    sort_order = "ASC" if operation.get("sort_order", "desc") == "asc" else "DESC"
    top_n = _normalized_limit(operation.get("limit"))
    warnings: list[str] = []

    if top_n == 1:
        # Check for ties
        sql = f"SELECT {select_expr} FROM [{table}] {where} GROUP BY [{group_by}] ORDER BY [{sort_by}] {sort_order}"
        all_rows = query(scenario_id, sql, params)
        if all_rows:
            top_value = all_rows[0].get(sort_by)
            tied = [r for r in all_rows if r.get(sort_by) == top_value]
            if len(tied) > 1:
                warnings.append(f"Ranking is ambiguous because {len(tied)} rows tie on {sort_by}.")
                rows = tied[:MAX_LIMIT]
            else:
                rows = all_rows[:1]
        else:
            rows = []
    else:
        sql = f"SELECT {select_expr} FROM [{table}] {where} GROUP BY [{group_by}] ORDER BY [{sort_by}] {sort_order} LIMIT ?"
        rows = query(scenario_id, sql, params + [top_n])

    result_columns = [group_by, value_column]
    return {
        "columns": result_columns,
        "rows": rows,
        "group_by": group_by,
        "value_column": value_column,
        "summary": f"Ranked {group_by} values from {operation['source']} using {agg}.",
        "warnings": warnings,
    }


def _aggregate_breakdown(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    table = _table_name(operation["source"])
    all_columns = get_table_columns(scenario_id, table)
    where, params = build_where_clause(operation.get("filters"), all_columns)

    group_by = _resolve_column(operation.get("group_by"), all_columns)
    if not group_by:
        return {
            "columns": [],
            "rows": [],
            "summary": f"Could not compute breakdown for {operation['source']} because group_by is missing or invalid.",
            "warnings": [f"Operation '{operation.get('title') or 'aggregate_breakdown'}' is missing a valid group_by column."],
        }

    metric = operation.get("metric")
    agg = operation.get("agg", "count")
    if metric and metric in all_columns and agg != "count":
        value_column = f"{metric}_{agg}"
        select_expr = f"[{group_by}], {_sql_agg(agg, metric)} AS [{value_column}]"
    else:
        value_column = "count"
        select_expr = f"[{group_by}], COUNT(*) AS [count]"

    sort_order = "ASC" if operation.get("sort_order", "desc") == "asc" else "DESC"
    limit = _normalized_limit(operation.get("limit"))

    sql = f"SELECT {select_expr} FROM [{table}] {where} GROUP BY [{group_by}] ORDER BY [{value_column}] {sort_order} LIMIT ?"
    rows = query(scenario_id, sql, params + [limit])

    result_columns = [group_by, value_column]
    return {
        "columns": result_columns,
        "rows": rows,
        "group_by": group_by,
        "value_column": value_column,
        "summary": f"Computed {group_by} breakdown from {operation['source']}.",
        "warnings": [],
        "unit": operation.get("unit"),
    }


def _aggregate_timeseries(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    table = _table_name(operation["source"])
    all_columns = get_table_columns(scenario_id, table)
    where, params = build_where_clause(operation.get("filters"), all_columns)

    date_column = operation.get("date_column") or _first_date_column(all_columns)
    if not date_column or date_column not in all_columns:
        return {
            "labels": [],
            "series": [],
            "summary": f"Could not compute time series for {operation['source']} because no date column was found.",
            "warnings": [f"Operation '{operation.get('title') or 'aggregate_timeseries'}' is missing a date column."],
        }

    granularity = operation.get("granularity", "day")
    group_by = _resolve_column(operation.get("group_by"), all_columns)
    metric = operation.get("metric")
    agg = operation.get("agg", "count")

    # Build date bucket expression
    if granularity == "week":
        bucket_expr = f"DATE([{date_column}], 'weekday 0', '-6 days')"
        label_format = "%Y-%m-%d"
    elif granularity == "month":
        bucket_expr = f"strftime('%Y-%m', [{date_column}])"
        label_format = "%Y-%m"
    else:  # day
        bucket_expr = f"DATE([{date_column}])"
        label_format = "%Y-%m-%d"

    # Build aggregation expression
    if metric and metric in all_columns and agg != "count":
        agg_expr = _sql_agg(agg, metric)
    else:
        agg_expr = "COUNT(*)"

    if group_by and group_by in all_columns:
        # Grouped timeseries → need to pivot in Python
        sql = (
            f"SELECT {bucket_expr} AS bucket, [{group_by}], {agg_expr} AS value "
            f"FROM [{table}] {where} "
            f"AND [{date_column}] IS NOT NULL "
            f"GROUP BY bucket, [{group_by}] "
            f"ORDER BY bucket"
        ) if where else (
            f"SELECT {bucket_expr} AS bucket, [{group_by}], {agg_expr} AS value "
            f"FROM [{table}] "
            f"WHERE [{date_column}] IS NOT NULL "
            f"GROUP BY bucket, [{group_by}] "
            f"ORDER BY bucket"
        )
        rows = query(scenario_id, sql, params)

        # Pivot: collect all buckets and group values
        all_buckets: list[str] = []
        groups: dict[str, dict[str, float]] = {}
        for row in rows:
            bucket = str(row["bucket"])
            grp = str(row[group_by])
            val = float(row["value"] or 0)
            if bucket not in all_buckets:
                all_buckets.append(bucket)
            if grp not in groups:
                groups[grp] = {}
            groups[grp][bucket] = val

        labels = all_buckets
        series = [
            {"name": grp, "values": [groups[grp].get(b, 0.0) for b in all_buckets]}
            for grp in sorted(groups.keys())
        ]
    else:
        # Simple timeseries (no group_by)
        sql = (
            f"SELECT {bucket_expr} AS bucket, {agg_expr} AS value "
            f"FROM [{table}] {where} "
            f"{'AND' if where else 'WHERE'} [{date_column}] IS NOT NULL "
            f"GROUP BY bucket "
            f"ORDER BY bucket"
        )
        rows = query(scenario_id, sql, params)
        labels = [str(r["bucket"]) for r in rows]
        series = [{"name": metric or "count", "values": [float(r["value"] or 0) for r in rows]}]

    return {
        "labels": labels,
        "series": series,
        "summary": f"Computed {granularity} time series from {operation['source']}.",
        "warnings": [],
        "unit": operation.get("unit"),
        "granularity": granularity,
        "group_by": group_by,
    }


def _compute_funnel(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    table = _table_name(operation["source"])
    all_columns = get_table_columns(scenario_id, table)
    where, params = build_where_clause(operation.get("filters"), all_columns)

    entity_column = operation.get("entity_column", "session_id")
    step_column = operation.get("step_column", "event_type")

    # Get available steps if not specified
    steps = operation.get("steps")
    if not steps:
        sql = f"SELECT DISTINCT [{step_column}] FROM [{table}] {where}"
        available = {str(r[step_column]) for r in query(scenario_id, sql, params)}
        steps = [s for s in FUNNEL_STEP_ORDER if s in available]

    labels: list[str] = []
    values: list[float] = []
    for step in steps:
        step_where = f"{where} AND" if where else "WHERE"
        if entity_column in all_columns:
            sql = f"SELECT COUNT(DISTINCT [{entity_column}]) AS cnt FROM [{table}] {step_where} [{step_column}] = ?"
        else:
            sql = f"SELECT COUNT(*) AS cnt FROM [{table}] {step_where} [{step_column}] = ?"
        result = query(scenario_id, sql, params + [step])
        labels.append(step)
        values.append(float(result[0]["cnt"]) if result else 0.0)

    return {
        "labels": labels,
        "series": [{"name": "count", "values": values}],
        "summary": f"Computed funnel from {operation['source']}.",
        "warnings": [],
    }


def _read_document_excerpt(scenario_id: str, operation: dict[str, Any], query_text: str) -> dict[str, Any]:
    source = operation["source"]
    content = get_document(scenario_id, source)
    if content is None:
        # Fallback: try reading from filesystem for non-migrated files
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent.parent / "scenarios" / scenario_id / "tables" / source
        if path.exists():
            content = path.read_text()
        else:
            return {
                "columns": ["term", "excerpt"],
                "rows": [],
                "summary": f"Document '{source}' not found.",
                "warnings": [f"Document '{source}' not found."],
            }

    search_terms = operation.get("terms") or _search_terms_from_query(query_text)
    excerpts: list[dict[str, str]] = []

    lowered = content.lower()
    for term in search_terms[:3]:
        idx = lowered.find(term.lower())
        if idx == -1:
            continue
        start = max(0, idx - 120)
        end = min(len(content), idx + 240)
        snippet = content[start:end].strip().replace("\n", " ")
        excerpts.append({"term": term, "excerpt": snippet})

    if not excerpts:
        fallback = content[:280].strip().replace("\n", " ")
        excerpts.append({"term": "preview", "excerpt": fallback})

    return {
        "columns": ["term", "excerpt"],
        "rows": excerpts,
        "summary": f"Found {len(excerpts)} excerpt(s) in {source}.",
        "warnings": [],
    }


def _summarize_source_profile(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    source = operation["source"]
    if source.endswith(".md"):
        content = get_document(scenario_id, source) or ""
        preview = content[:220].strip().replace("\n", " ")
        return {
            "columns": ["property", "value"],
            "rows": [
                {"property": "source_type", "value": "document"},
                {"property": "preview", "value": preview},
            ],
            "summary": f"{source} is a reference document with narrative evidence rather than row-based records.",
            "warnings": [],
        }

    table = _table_name(source)
    columns = get_table_columns(scenario_id, table)
    date_column = operation.get("date_column") or _first_date_column(columns)
    row_count = get_table_row_count(scenario_id, table)
    sample_fields = ", ".join(columns[:6])
    span_text = ""
    rows = [
        {"property": "rows", "value": row_count},
        {"property": "fields", "value": sample_fields},
    ]
    if date_column:
        min_date = query_value(scenario_id, f"SELECT MIN([{date_column}]) FROM [{table}] WHERE [{date_column}] IS NOT NULL")
        max_date = query_value(scenario_id, f"SELECT MAX([{date_column}]) FROM [{table}] WHERE [{date_column}] IS NOT NULL")
        if min_date and max_date:
            span_text = f" It spans {min_date} to {max_date}."
            rows.extend([
                {"property": "date_column", "value": date_column},
                {"property": "min_date", "value": min_date},
                {"property": "max_date", "value": max_date},
            ])
    return {
        "columns": ["property", "value"],
        "rows": rows,
        "summary": f"{source} contains {row_count} rows with fields like {sample_fields}.{span_text}".strip(),
        "warnings": [],
    }


def _summarize_date_span(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    source = operation["source"]
    table = _table_name(source)
    columns = get_table_columns(scenario_id, table)
    date_column = operation.get("date_column") or _first_date_column(columns)
    if not date_column:
        return {
            "columns": ["property", "value"],
            "rows": [],
            "summary": f"Could not determine a date span for {source} because no date column was found.",
            "warnings": [f"Operation '{operation.get('title') or 'summarize_date_span'}' is missing a valid date column."],
        }

    min_date = query_value(scenario_id, f"SELECT MIN([{date_column}]) FROM [{table}] WHERE [{date_column}] IS NOT NULL")
    max_date = query_value(scenario_id, f"SELECT MAX([{date_column}]) FROM [{table}] WHERE [{date_column}] IS NOT NULL")
    row_count = get_table_row_count(scenario_id, table)
    day_count = query_value(
        scenario_id,
        f"SELECT CAST((julianday(MAX([{date_column}])) - julianday(MIN([{date_column}]))) AS INTEGER) + 1 FROM [{table}] WHERE [{date_column}] IS NOT NULL",
    )
    return {
        "columns": ["property", "value"],
        "rows": [
            {"property": "date_column", "value": date_column},
            {"property": "min_date", "value": min_date},
            {"property": "max_date", "value": max_date},
            {"property": "days_covered", "value": day_count},
            {"property": "row_count", "value": row_count},
        ],
        "summary": f"{source} spans {min_date} through {max_date}, covering {day_count} day(s) across {row_count} row(s).",
        "warnings": [],
        "date_column": date_column,
    }


def _compare_segments(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    table = _table_name(operation["source"])
    all_columns = get_table_columns(scenario_id, table)
    group_by = _resolve_column(operation.get("group_by"), all_columns)
    date_column = operation.get("date_column") or _first_date_column(all_columns)
    split_date = operation.get("split_date")
    if not group_by or not date_column or not split_date:
        return {
            "columns": [],
            "rows": [],
            "summary": f"Could not compare segments for {operation['source']} because group_by, split_date, or date_column is missing.",
            "warnings": [f"Operation '{operation.get('title') or 'compare_segments'}' is missing group_by, split_date, or date_column."],
        }

    metric = operation.get("metric")
    agg = operation.get("agg", "count")
    if metric and metric in all_columns and agg != "count":
        agg_expr = _sql_agg(agg, metric)
    else:
        agg_expr = "COUNT(*)"

    before_rows = query(
        scenario_id,
        f"SELECT [{group_by}] AS segment, {agg_expr} AS value FROM [{table}] WHERE [{date_column}] < ? GROUP BY [{group_by}]",
        (split_date,),
    )
    after_rows = query(
        scenario_id,
        f"SELECT [{group_by}] AS segment, {agg_expr} AS value FROM [{table}] WHERE [{date_column}] >= ? GROUP BY [{group_by}]",
        (split_date,),
    )
    before_map = {str(row["segment"]): float(row["value"] or 0) for row in before_rows}
    after_map = {str(row["segment"]): float(row["value"] or 0) for row in after_rows}
    segments = sorted(set(before_map) | set(after_map))
    rows = []
    for segment in segments:
        before_value = before_map.get(segment, 0.0)
        after_value = after_map.get(segment, 0.0)
        delta_pct = None if before_value == 0 else round(((after_value - before_value) / before_value) * 100, 1)
        rows.append({
            group_by: segment,
            "before_value": round(before_value, 2),
            "after_value": round(after_value, 2),
            "delta_pct": delta_pct,
        })
    rows.sort(key=lambda row: abs(row.get("delta_pct") or 0), reverse=True)
    return {
        "columns": [group_by, "before_value", "after_value", "delta_pct"],
        "rows": rows[:MAX_LIMIT],
        "group_by": group_by,
        "value_column": "delta_pct",
        "summary": f"Compared {group_by} segments before and after {split_date} in {operation['source']}.",
        "warnings": [],
        "unit": "%",
    }


def _summarize_metric_delta(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    table = _table_name(operation["source"])
    all_columns = get_table_columns(scenario_id, table)
    date_column = operation.get("date_column") or _first_date_column(all_columns)
    split_date = operation.get("split_date")
    if not date_column or not split_date:
        return {
            "columns": [],
            "rows": [],
            "summary": f"Could not compare pre/post metrics for {operation['source']} because split_date or date_column is missing.",
            "warnings": [f"Operation '{operation.get('title') or 'summarize_metric_delta'}' is missing split_date or date_column."],
        }
    metric = operation.get("metric")
    agg = operation.get("agg", "count")
    agg_expr = _sql_agg(agg, metric) if metric and metric in all_columns and agg != "count" else "COUNT(*)"
    before_value = query_value(scenario_id, f"SELECT {agg_expr} FROM [{table}] WHERE [{date_column}] < ?", (split_date,)) or 0
    after_value = query_value(scenario_id, f"SELECT {agg_expr} FROM [{table}] WHERE [{date_column}] >= ?", (split_date,)) or 0
    delta_pct = None if float(before_value or 0) == 0 else round(((float(after_value) - float(before_value)) / float(before_value)) * 100, 1)
    return {
        "columns": ["before_value", "after_value", "delta_pct"],
        "rows": [{"before_value": before_value, "after_value": after_value, "delta_pct": delta_pct}],
        "value_column": "delta_pct",
        "summary": f"Compared {operation.get('metric') or 'count'} before and after {split_date} in {operation['source']}.",
        "warnings": [],
        "unit": "%",
    }


def _extract_feedback_themes(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    source = operation["source"]
    table = _table_name(source)
    columns = get_table_columns(scenario_id, table)
    text_columns = [col for col in ("text", "description", "subcategory", "category") if col in columns]
    if not text_columns:
        return {
            "columns": [],
            "rows": [],
            "summary": f"Could not extract themes from {source} because no text-bearing columns were found.",
            "warnings": [f"Operation '{operation.get('title') or 'extract_feedback_themes'}' could not find text columns."],
        }
    select_cols = ", ".join(f"[{col}]" for col in text_columns)
    rows = query(scenario_id, f"SELECT {select_cols} FROM [{table}] LIMIT 500")
    themes = _count_theme_hits(rows, text_columns)
    theme_rows = [{"theme": theme, "count": count} for theme, count in themes]
    return {
        "columns": ["theme", "count"],
        "rows": theme_rows,
        "group_by": "theme",
        "value_column": "count",
        "summary": f"Extracted recurring feedback themes from {source}.",
        "warnings": [],
    }


def _select_representative_quotes(scenario_id: str, operation: dict[str, Any], query_text: str) -> dict[str, Any]:
    source = operation["source"]
    table = _table_name(source)
    columns = get_table_columns(scenario_id, table)
    quote_column = "text" if "text" in columns else "description" if "description" in columns else None
    if not quote_column:
        return {
            "columns": [],
            "rows": [],
            "summary": f"Could not select quotes from {source} because no quote column was found.",
            "warnings": [f"Operation '{operation.get('title') or 'select_representative_quotes'}' is missing a quote column."],
        }
    where, params = build_where_clause(operation.get("filters"), columns)
    limit = _normalized_limit(operation.get("limit", 5))
    sql = f"SELECT * FROM [{table}] {where} ORDER BY [{_first_date_column(columns) or columns[0]}] DESC LIMIT ?"
    rows = query(scenario_id, sql, params + [limit])
    normalized_rows = []
    for row in rows:
        normalized_rows.append({
            "quote": row.get(quote_column),
            "platform": row.get("platform"),
            "city": row.get("city"),
            "created_at": row.get(_first_date_column(columns) or ""),
        })
    return {
        "columns": ["quote", "platform", "city", "created_at"],
        "rows": normalized_rows,
        "summary": f"Selected representative quotes from {source} relevant to the current UX question.",
        "warnings": [],
    }


def _count_issue_mentions(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    result = _extract_feedback_themes(scenario_id, operation)
    result["summary"] = f"Counted issue mentions in {operation['source']}."
    result["title"] = operation.get("title") or "Issue mention counts"
    return result


def _summarize_ux_change_impact(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    source = operation["source"]
    table = _table_name(source)
    columns = get_table_columns(scenario_id, table)
    where, params = build_where_clause(operation.get("filters"), columns)
    limit = _normalized_limit(operation.get("limit", 8))
    sql = f"SELECT [date], [change_type], [affected_area], [description] FROM [{table}] {where} ORDER BY [date] DESC LIMIT ?"
    rows = query(scenario_id, sql, params + [limit])
    return {
        "columns": ["date", "change_type", "affected_area", "description"],
        "rows": rows,
        "summary": f"Summarized recent UX changes from {source}.",
        "warnings": [],
    }


def _build_incident_timeline(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    source = operation["source"]
    table = _table_name(source)
    columns = get_table_columns(scenario_id, table)
    date_column = operation.get("date_column") or _first_date_column(columns) or columns[0]
    visible_columns = [col for col in (date_column, "service", "description", "author", "rollback_available", "error_code", "count", "platform") if col in columns]
    where, params = build_where_clause(operation.get("filters"), columns)
    limit = _normalized_limit(operation.get("limit", 10))
    sql = f"SELECT {', '.join(f'[{col}]' for col in visible_columns)} FROM [{table}] {where} ORDER BY [{date_column}] DESC LIMIT ?"
    rows = query(scenario_id, sql, params + [limit])
    return {
        "columns": visible_columns,
        "rows": rows,
        "summary": f"Built an incident timeline from {source}.",
        "warnings": [],
    }


def _correlate_deployments_with_metrics(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    metric_source = operation.get("source", "service_metrics.csv")
    deploy_source = operation.get("deployment_source", "deployments.csv")
    split_date = operation.get("split_date") or "2025-01-10"
    metric_table = _table_name(metric_source)
    deploy_table = _table_name(deploy_source)
    metric_column = operation.get("metric", "error_rate_pct")
    service_filter = operation.get("filters", {}).get("service") if isinstance(operation.get("filters"), dict) else None
    service_clause = "WHERE [service] = ?" if service_filter else ""
    params = [service_filter] if service_filter else []
    before_value = query_value(scenario_id, f"SELECT AVG([{metric_column}]) FROM [{metric_table}] {service_clause} {'AND' if service_clause else 'WHERE'} [date] < ?", params + [split_date]) or 0
    after_value = query_value(scenario_id, f"SELECT AVG([{metric_column}]) FROM [{metric_table}] {service_clause} {'AND' if service_clause else 'WHERE'} [date] >= ?", params + [split_date]) or 0
    recent_deploys = query(
        scenario_id,
        f"SELECT [timestamp], [service], [description] FROM [{deploy_table}] WHERE DATE([timestamp]) >= DATE(?, '-3 days') AND DATE([timestamp]) <= DATE(?, '+3 days') ORDER BY [timestamp]",
        (split_date, split_date),
    )
    delta_pct = None if float(before_value or 0) == 0 else round(((float(after_value) - float(before_value)) / float(before_value)) * 100, 1)
    rows = [{
        "metric": metric_column,
        "before_value": round(float(before_value), 2),
        "after_value": round(float(after_value), 2),
        "delta_pct": delta_pct,
        "nearby_deployments": len(recent_deploys),
    }]
    return {
        "columns": ["metric", "before_value", "after_value", "delta_pct", "nearby_deployments"],
        "rows": rows,
        "value_column": "delta_pct",
        "summary": f"Compared {metric_column} before and after {split_date} and counted nearby deployments.",
        "warnings": [],
        "unit": "%",
    }


def _summarize_error_shift(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    source = operation["source"]
    table = _table_name(source)
    split_date = operation.get("split_date") or "2025-01-10"
    before_rows = query(
        scenario_id,
        f"SELECT [error_code], SUM([count]) AS value FROM [{table}] WHERE [date] < ? GROUP BY [error_code]",
        (split_date,),
    )
    after_rows = query(
        scenario_id,
        f"SELECT [error_code], SUM([count]) AS value FROM [{table}] WHERE [date] >= ? GROUP BY [error_code]",
        (split_date,),
    )
    before_map = {str(row["error_code"]): float(row["value"] or 0) for row in before_rows}
    after_map = {str(row["error_code"]): float(row["value"] or 0) for row in after_rows}
    error_codes = sorted(set(before_map) | set(after_map))
    rows = []
    for error_code in error_codes:
        before_value = before_map.get(error_code, 0.0)
        after_value = after_map.get(error_code, 0.0)
        delta_pct = None if before_value == 0 else round(((after_value - before_value) / before_value) * 100, 1)
        rows.append({
            "error_code": error_code,
            "before_count": round(before_value),
            "after_count": round(after_value),
            "delta_pct": delta_pct,
        })
    rows.sort(key=lambda row: abs(row.get("delta_pct") or 0), reverse=True)
    return {
        "columns": ["error_code", "before_count", "after_count", "delta_pct"],
        "rows": rows[:MAX_LIMIT],
        "group_by": "error_code",
        "value_column": "delta_pct",
        "summary": f"Summarized how payment error patterns shifted after {split_date}.",
        "warnings": [],
        "unit": "%",
    }


def _compare_pre_post_rollout(scenario_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    return _summarize_metric_delta(scenario_id, operation)


# ────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────


def _sql_agg(agg: str, column: str) -> str:
    """Convert agg name to SQL aggregate expression."""
    agg_map = {
        "sum": f"SUM([{column}])",
        "mean": f"AVG([{column}])",
        "avg": f"AVG([{column}])",
        "min": f"MIN([{column}])",
        "max": f"MAX([{column}])",
        "count": "COUNT(*)",
        "count_unique": f"COUNT(DISTINCT [{column}])",
    }
    return agg_map.get(agg, f"SUM([{column}])")


def _artifact_metadata(
    item: dict[str, Any],
    agent: str,
    intent_class: str,
    capability_profile: dict[str, Any],
    query_text: str,
) -> dict[str, Any]:
    op_type = str(item.get("operation") or "")
    summary = str(item.get("summary") or item.get("title") or query_text).strip()
    purpose = _determine_artifact_purpose(item, intent_class)
    display_mode = _determine_display_mode(item, intent_class, query_text, capability_profile)
    confidence = _determine_confidence(item, intent_class)
    card_variant = _default_card_variant_from_evidence(item, agent)
    return {
        "purpose": purpose,
        "display_mode": display_mode,
        "summary": summary,
        "source_role": agent,
        "confidence": confidence,
        "card_variant": card_variant,
        "operation_type": op_type,
    }


def _determine_artifact_purpose(item: dict[str, Any], intent_class: str) -> str:
    if intent_class in {"reference", "dataset_summary", "schema_question"}:
        return "reference"
    if item.get("operation") in {"lookup_rows", "read_document_excerpt"} and not _rows_are_intrinsically_evidentiary(item):
        return "scratch"
    if intent_class in {"root_cause_analysis", "incident_timeline"}:
        return "final_evidence"
    if item.get("operation") in {"extract_feedback_themes", "select_representative_quotes", "build_incident_timeline", "summarize_error_shift"}:
        return "final_evidence"
    return "supporting_evidence"


def _determine_display_mode(
    item: dict[str, Any],
    intent_class: str,
    query_text: str,
    capability_profile: dict[str, Any],
) -> str:
    if intent_class in set(capability_profile.get("board_eligibility_rules", {}).get("inline_only_intents", [])):
        return "inline_only"
    lowered = query_text.lower()
    if item.get("operation") in {"lookup_rows", "read_document_excerpt"} and not _rows_are_intrinsically_evidentiary(item):
        return "inline_only"
    if any(token in lowered for token in ("save as evidence", "add to board")):
        return "board_default"
    if any(token in lowered for token in ("show", "plot", "compare")):
        return "board_default"
    if item.get("operation") in {"compute_funnel", "aggregate_timeseries", "aggregate_breakdown", "extract_feedback_themes", "select_representative_quotes", "build_incident_timeline", "summarize_error_shift"}:
        return "board_default"
    return "board_optional"


def _determine_confidence(item: dict[str, Any], intent_class: str) -> str:
    warnings = item.get("warnings") or []
    if warnings:
        return "low"
    if intent_class in {"reference", "dataset_summary", "schema_question"}:
        return "high"
    if item.get("operation") in {"compute_funnel", "aggregate_timeseries", "aggregate_breakdown", "summarize_error_shift", "extract_feedback_themes"}:
        return "high"
    return "medium"


def _rows_are_intrinsically_evidentiary(item: dict[str, Any]) -> bool:
    columns = [str(col).lower() for col in item.get("columns", [])]
    rows = item.get("rows") or []
    if not rows:
        return False
    if "quote" in columns or "excerpt" in columns:
        return True
    if "delta_pct" in columns or "error_code" in columns or "theme" in columns:
        return True
    if "description" in columns and "service" in columns:
        return True
    return False


def _default_card_variant_from_evidence(item: dict[str, Any], agent: str) -> str:
    op_type = str(item.get("operation") or "")
    if op_type in {"select_representative_quotes", "extract_feedback_themes"}:
        return "quote"
    if op_type in {"build_incident_timeline", "correlate_deployments_with_metrics", "summarize_error_shift", "compare_pre_post_rollout"}:
        return "timeline" if agent == "engineering_lead" else "table"
    if op_type in {"aggregate_timeseries", "aggregate_breakdown", "compute_funnel"}:
        return "chart"
    return "finding"


def _default_card_variant(artifact: dict[str, Any]) -> str:
    if artifact.get("card_variant"):
        return str(artifact["card_variant"])
    if artifact.get("kind") == "chart":
        return "chart"
    if artifact.get("kind") == "table":
        return "table"
    return "finding"


def _artifact_supports_board(artifact: dict[str, Any]) -> bool:
    if artifact.get("purpose") in {"reference", "scratch"}:
        return False
    if artifact.get("kind") == "table":
        columns = [str(col).lower() for col in artifact.get("columns", [])]
        rows = artifact.get("rows") or []
        if not rows:
            return False
        if columns == ["property", "value"] and artifact.get("purpose") != "final_evidence":
            return False
        if "preview" in columns:
            return False
        if len(columns) > 6 and artifact.get("purpose") != "final_evidence":
            return False
    return True


def _count_theme_hits(rows: list[dict[str, Any]], text_columns: list[str]) -> list[tuple[str, int]]:
    theme_terms = {
        "payment_failure": ["debited", "failed", "payment", "timeout", "upi", "bank", "callback"],
        "retry_confusion": ["retry", "again", "stuck", "processing", "spinner", "waiting"],
        "trust_damage": ["trust", "switched", "another app", "refund", "money"],
        "ux_clarity": ["unclear", "confusing", "confirmation", "status", "message"],
    }
    counts = {theme: 0 for theme in theme_terms}
    for row in rows:
        blob = " ".join(str(row.get(column) or "") for column in text_columns).lower()
        for theme, keywords in theme_terms.items():
            if any(keyword in blob for keyword in keywords):
                counts[theme] += 1
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [item for item in ordered if item[1] > 0][:6]


def _validate_columns(columns: list[str] | None, all_columns: list[str]) -> list[str]:
    if not columns:
        return []
    return [c for c in columns if c in all_columns]


def _first_date_column(columns: list[str]) -> str | None:
    for column in columns:
        lowered = column.lower()
        if any(token in lowered for token in ("date", "time", "_at", "timestamp")):
            return column
    return None


def _normalized_limit(value: Any) -> int:
    if not value:
        return DEFAULT_LIMIT
    try:
        return max(1, min(int(value), MAX_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def _resolve_templates(value: Any, alias_results: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_templates(item, alias_results) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_templates(item, alias_results) for item in value]
    if isinstance(value, str) and value.startswith("$"):
        return _resolve_pointer(value[1:], alias_results)
    return value


def _resolve_pointer(pointer: str, alias_results: dict[str, dict[str, Any]]) -> Any:
    parts = pointer.split(".")
    current: Any = alias_results.get(parts[0])
    for part in parts[1:]:
        if current is None:
            return None
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _search_terms_from_query(query_text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z_]{4,}", query_text)
    return [token.lower() for token in tokens[:5]]


def _default_title(op_type: str, source: str | None, query_text: str) -> str:
    if source:
        return f"{source}: {query_text[:60]}".strip()
    return f"{op_type}: {query_text[:60]}".strip()


def _resolve_result_title(
    op_type: str,
    operation: dict[str, Any],
    result: dict[str, Any],
    query_text: str,
) -> tuple[str, str | None]:
    requested_title = (operation.get("title") or "").strip()
    if op_type == "aggregate_timeseries":
        derived_title = _timeseries_title(operation, result, query_text)
        if requested_title and _title_granularity_conflicts(requested_title, result.get("granularity")):
            warning = (
                f"Renamed artifact from '{requested_title}' to '{derived_title}' because the computed granularity is "
                f"{result.get('granularity')}."
            )
            return derived_title, warning
        return derived_title, None
    if op_type == "summarize_source_profile":
        return requested_title or f"{operation.get('source')} source profile", None
    if op_type == "summarize_date_span":
        return requested_title or f"{operation.get('source')} date coverage", None
    if op_type == "extract_feedback_themes":
        return requested_title or f"{operation.get('source')} feedback themes", None
    if op_type == "select_representative_quotes":
        return requested_title or f"{operation.get('source')} representative quotes", None
    if op_type == "build_incident_timeline":
        return requested_title or f"{operation.get('source')} incident timeline", None
    if op_type == "summarize_error_shift":
        return requested_title or f"{operation.get('source')} error shift", None
    return requested_title or result.get("title") or _default_title(op_type, operation.get("source"), query_text), None


def _timeseries_title(operation: dict[str, Any], result: dict[str, Any], query_text: str) -> str:
    granularity = str(result.get("granularity") or operation.get("granularity") or "day").lower()
    group_by = operation.get("group_by")
    source = str(operation.get("source") or result.get("source") or "").lower()
    metric_label = "Orders" if "orders" in source else "Trend"
    prefix = {
        "day": "Daily",
        "week": "Weekly",
        "month": "Monthly",
    }.get(granularity, granularity.title())
    if group_by:
        return f"{prefix} {metric_label} by {str(group_by).replace('_', ' ').title()}"
    if "payment" in query_text.lower() and "payments" in source:
        metric_label = "Payments"
    return f"{prefix} {metric_label} Trend"


def _title_granularity_conflicts(title: str, granularity: Any) -> bool:
    lowered = title.lower()
    granularity_text = str(granularity or "day").lower()
    if "monthly" in lowered and granularity_text != "month":
        return True
    if "weekly" in lowered and granularity_text != "week":
        return True
    if "daily" in lowered and granularity_text != "day":
        return True
    return False


def _unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
