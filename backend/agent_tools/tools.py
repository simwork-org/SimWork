"""Generic data tools for agentic agents.

Three primitives that replace all rigid skill functions:
  - query_table: flexible querying with filters, group_by, aggregation
  - read_document: returns markdown/text file contents
  - describe_tables: schema info for all accessible tables

Each tool validates that the agent has access to the requested table
via AGENT_TABLE_ACCESS before operating.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from data_layer.db import (
    build_where_clause,
    get_distinct_value_previews,
    get_document,
    get_sample_rows,
    get_table_columns,
    get_table_row_count,
    get_table_schema,
    query,
    query_value,
    table_exists,
)
from telemetry_layer.telemetry import AGENT_TABLE_ACCESS

logger = logging.getLogger(__name__)

MAX_RESULT_ROWS = 50


# ────────────────────────────────────────────────────
# Access control
# ────────────────────────────────────────────────────


def _validate_access(agent: str, table: str) -> None:
    """Raise if the agent is not allowed to access this table."""
    allowed = AGENT_TABLE_ACCESS.get(agent, [])
    if table not in allowed:
        raise PermissionError(
            f"Agent '{agent}' does not have access to '{table}'. "
            f"Accessible tables: {allowed}"
        )


def query_table(
    scenario_id: str,
    agent: str,
    table: str,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    group_by: str | None = None,
    agg: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    limit: int | None = None,
) -> str:
    """Query a table with optional filters, grouping, aggregation, sorting.

    Args:
        table: canonical database table name (e.g. "orders")
        columns: Optional list of columns to return
        filters: Dict of column_name -> value or operator conditions
        group_by: Column to group by
        agg: Aggregation function: count, sum, mean, min, max, count_unique, or
             column-specific like "sum:total_amount" or "mean:processing_time_ms"
        sort_by: Column to sort by
        sort_order: "asc" or "desc" (default "desc")
        limit: Max rows to return

    Returns:
        JSON string with query results.
    """
    _validate_access(agent, table)

    if not table_exists(scenario_id, table):
        return json.dumps({"error": f"Table not found: {table}"})

    all_columns = get_table_columns(scenario_id, table)
    where, params = build_where_clause(filters, all_columns)

    effective_limit = min(limit or MAX_RESULT_ROWS, MAX_RESULT_ROWS)

    if group_by and group_by in all_columns:
        # Grouped query
        agg_fn = agg or "count"
        select_expr, val_col = _build_group_select(group_by, agg_fn, all_columns)

        # Count total groups
        count_sql = f"SELECT COUNT(*) FROM (SELECT [{group_by}] FROM [{table}] {where} GROUP BY [{group_by}])"
        total_rows = query_value(scenario_id, count_sql, params) or 0

        # Sort
        order_col = sort_by if sort_by and sort_by in (all_columns + [val_col]) else val_col
        direction = "ASC" if sort_order == "asc" else "DESC"

        sql = f"SELECT {select_expr} FROM [{table}] {where} GROUP BY [{group_by}] ORDER BY [{order_col}] {direction} LIMIT ?"
        data = query(scenario_id, sql, params + [effective_limit])
        result_columns = list(data[0].keys()) if data else [group_by, val_col]
    else:
        # Non-grouped query
        if columns:
            valid_cols = [c for c in columns if c in all_columns]
            select_cols = ", ".join(f"[{c}]" for c in valid_cols) if valid_cols else "*"
        else:
            select_cols = "*"

        # Count total matching rows
        count_sql = f"SELECT COUNT(*) FROM [{table}] {where}"
        total_rows = query_value(scenario_id, count_sql, params) or 0

        order_clause = ""
        if sort_by and sort_by in all_columns:
            direction = "ASC" if sort_order == "asc" else "DESC"
            order_clause = f"ORDER BY [{sort_by}] {direction}"

        sql = f"SELECT {select_cols} FROM [{table}] {where} {order_clause} LIMIT ?"
        data = query(scenario_id, sql, params + [effective_limit])
        result_columns = list(data[0].keys()) if data else all_columns

    result = {
        "table": table,
        "total_matching_rows": total_rows,
        "returned_rows": len(data),
        "columns": result_columns,
        "data": data,
    }
    if total_rows > effective_limit:
        result["note"] = f"Showing top {effective_limit} of {total_rows} rows. Refine filters for more specific results."

    return json.dumps(result, default=str)


def _build_group_select(group_by: str, agg_fn: str, all_columns: list[str]) -> tuple[str, str]:
    """Build SELECT expression for grouped queries. Returns (select_expr, value_column_name)."""
    if ":" in agg_fn:
        fn_name, agg_col = agg_fn.split(":", 1)
        if agg_col in all_columns:
            if fn_name == "count_unique":
                val_col = f"{agg_col}_unique_count"
                return f"[{group_by}], COUNT(DISTINCT [{agg_col}]) AS [{val_col}]", val_col
            else:
                sql_fn = {"sum": "SUM", "mean": "AVG", "avg": "AVG", "min": "MIN", "max": "MAX"}.get(fn_name, "SUM")
                val_col = f"{agg_col}_{fn_name}"
                return f"[{group_by}], {sql_fn}([{agg_col}]) AS [{val_col}]", val_col
        return f"[{group_by}], COUNT(*) AS [count]", "count"

    if agg_fn == "count":
        return f"[{group_by}], COUNT(*) AS [count]", "count"
    if agg_fn == "count_unique":
        other_cols = [c for c in all_columns if c != group_by]
        if other_cols:
            val_col = f"{other_cols[0]}_unique_count"
            return f"[{group_by}], COUNT(DISTINCT [{other_cols[0]}]) AS [{val_col}]", val_col
        return f"[{group_by}], COUNT(*) AS [count]", "count"

    # Apply agg to all numeric-like columns — just use count as fallback
    return f"[{group_by}], COUNT(*) AS [count]", "count"


# ────────────────────────────────────────────────────
# Tool 2: read_document
# ────────────────────────────────────────────────────


def read_document(scenario_id: str, agent: str, filename: str) -> str:
    """Read a markdown or text file from the scenario data.

    Returns the full content of the file.
    """
    _validate_access(agent, filename)

    content = get_document(scenario_id, filename)
    if content is None:
        return json.dumps({"error": f"Document not found: {filename}"})

    return json.dumps({"filename": filename, "content": content})


# ────────────────────────────────────────────────────
# Tool 3: describe_tables
# ────────────────────────────────────────────────────


def describe_tables(scenario_id: str, agent: str) -> str:
    """List all accessible tables with schema info.

    For each source: name, schema, row count, sample rows, and low-cardinality distinct values.
    """
    allowed = AGENT_TABLE_ACCESS.get(agent, [])
    tables_info = []

    for filename in allowed:
        if filename.endswith(".md"):
            content = get_document(scenario_id, filename)
            if content is None:
                tables_info.append({"name": filename, "status": "not_found"})
                continue
            tables_info.append({
                "name": filename,
                "type": "markdown",
                "size_chars": len(content),
                "preview": content[:300] + ("..." if len(content) > 300 else ""),
            })
            continue

        if table_exists(scenario_id, filename):
            schema = get_table_schema(scenario_id, filename)
            col_info = [{"name": s["name"], "dtype": s["type"]} for s in schema]
            row_count = get_table_row_count(scenario_id, filename)
            sample = get_sample_rows(scenario_id, filename, 2)

            # Date range detection
            date_cols = [s["name"] for s in schema if any(kw in s["name"].lower() for kw in ("date", "timestamp", "created_at", "_at"))]
            date_range = None
            if date_cols:
                dc = date_cols[0]
                try:
                    min_val = query_value(scenario_id, f"SELECT MIN([{dc}]) FROM [{filename}]")
                    max_val = query_value(scenario_id, f"SELECT MAX([{dc}]) FROM [{filename}]")
                    if min_val and max_val:
                        date_range = {"column": dc, "min": str(min_val), "max": str(max_val)}
                except Exception:
                    pass

            info: dict[str, Any] = {
                "name": filename,
                "type": "table",
                "rows": row_count,
                "columns": col_info,
                "sample": sample,
                "distinct_value_previews": get_distinct_value_previews(scenario_id, filename),
            }
            if date_range:
                info["date_range"] = date_range
            tables_info.append(info)
        else:
            tables_info.append({"name": filename, "type": "unknown"})

    return json.dumps({"agent": agent, "accessible_tables": tables_info}, default=str)


# ────────────────────────────────────────────────────
# Tool definitions (OpenAI function-calling format)
# ────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_table",
            "description": (
                "Query a database table with optional filtering, grouping, and aggregation. "
                "Use this for any data analysis: trends, breakdowns, comparisons, counts, etc. "
                "You can call this multiple times to investigate from different angles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Database table to query (e.g. 'orders', 'payments')",
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of columns to return. Omit to return all.",
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            "Optional filters. Keys are 'column_name' for exact match, "
                            "'column_name >' for comparison, or 'column_name contains' for substring search. "
                            "Examples: {\"platform\": \"ios\"}, {\"error_rate_pct >\": 1.0}, {\"text contains\": \"payment\"}"
                        ),
                    },
                    "group_by": {
                        "type": "string",
                        "description": "Column to group results by.",
                    },
                    "agg": {
                        "type": "string",
                        "description": (
                            "Aggregation: 'count', 'sum', 'mean', 'min', 'max', 'count_unique', "
                            "or column-specific like 'sum:total_amount', 'mean:processing_time_ms', 'count_unique:user_id'."
                        ),
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Column to sort results by.",
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort direction. Default: 'desc'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return (capped at 50).",
                    },
                },
                "required": ["table"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": (
                "Read a markdown or text document from the data sources. "
                "Use this for qualitative data like architecture docs, usability studies, or changelogs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The document filename (e.g. 'system_architecture.md', 'usability_study.md')",
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_tables",
            "description": (
                "List all data tables you have access to, with column names, data types, row counts, "
                "date ranges, and sample rows. Call this when you need to understand what data is available "
                "or when someone asks about your data sources."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]
