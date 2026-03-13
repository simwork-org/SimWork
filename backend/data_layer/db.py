"""SQLite data layer — single connection per scenario, query helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "scenarios"

# Cache open connections (one per scenario)
_connections: dict[str, sqlite3.Connection] = {}


def _db_path(scenario_id: str) -> Path:
    return SCENARIOS_DIR / scenario_id / "tables" / "scenario.db"


def get_connection(scenario_id: str) -> sqlite3.Connection:
    """Return a cached SQLite connection for the given scenario."""
    if scenario_id not in _connections:
        path = _db_path(scenario_id)
        if not path.exists():
            raise FileNotFoundError(
                f"Database not found: {path}. Run: python scripts/csv_to_sqlite.py {scenario_id}"
            )
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _connections[scenario_id] = conn
    return _connections[scenario_id]


def query(scenario_id: str, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    """Execute a SQL query and return results as a list of dicts."""
    conn = get_connection(scenario_id)
    cursor = conn.execute(sql, params)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def query_value(scenario_id: str, sql: str, params: tuple | list = ()) -> Any:
    """Execute a SQL query and return the first column of the first row."""
    conn = get_connection(scenario_id)
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    return row[0] if row else None


def get_table_schema(scenario_id: str, table: str) -> list[dict[str, str]]:
    """Return column info for a table: [{name, type}, ...]."""
    rows = query(scenario_id, f"PRAGMA table_info([{table}])")
    return [{"name": r["name"], "type": r["type"]} for r in rows]


def get_table_columns(scenario_id: str, table: str) -> list[str]:
    """Return column names for a table."""
    return [col["name"] for col in get_table_schema(scenario_id, table)]


def get_table_row_count(scenario_id: str, table: str) -> int:
    """Return the number of rows in a table."""
    return query_value(scenario_id, f"SELECT COUNT(*) FROM [{table}]") or 0


def table_exists(scenario_id: str, table: str) -> bool:
    """Check if a table exists in the database."""
    count = query_value(
        scenario_id,
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return bool(count)


def get_document(scenario_id: str, name: str) -> str | None:
    """Read a markdown document from the documents table."""
    result = query_value(
        scenario_id,
        "SELECT content FROM documents WHERE name = ?",
        (name,),
    )
    return result


def get_sample_rows(scenario_id: str, table: str, n: int = 3) -> list[dict[str, Any]]:
    """Return the first n rows of a table."""
    return query(scenario_id, f"SELECT * FROM [{table}] LIMIT ?", (n,))


def close_all() -> None:
    """Close all cached connections."""
    for conn in _connections.values():
        conn.close()
    _connections.clear()


# ────────────────────────────────────────────────────
# SQL building helpers
# ────────────────────────────────────────────────────


def build_where_clause(
    filters: dict[str, Any] | None,
    valid_columns: list[str],
) -> tuple[str, list[Any]]:
    """Convert evidence-style filters dict to a SQL WHERE clause.

    Filter key formats:
      "column"           → exact match (column = ?)
      "column >"         → column > ?
      "column <"         → column < ?
      "column >="        → column >= ?
      "column <="        → column <= ?
      "column !="        → column != ?
      "column contains"  → column LIKE '%?%'

    Returns (where_sql, params) — where_sql includes "WHERE ..." or is empty.
    """
    if not filters:
        return "", []

    clauses: list[str] = []
    params: list[Any] = []

    for raw_key, value in filters.items():
        key = str(raw_key).strip()

        # "column contains"
        if key.endswith(" contains"):
            column = key[:-9].strip()
            if column in valid_columns:
                clauses.append(f"[{column}] LIKE ?")
                params.append(f"%{value}%")
            continue

        # "column OP"
        parts = key.rsplit(" ", 1)
        if len(parts) == 2 and parts[1] in (">", "<", ">=", "<=", "!="):
            column, op = parts
            if column in valid_columns:
                clauses.append(f"[{column}] {op} ?")
                params.append(value)
            continue

        # Exact match
        if key in valid_columns:
            clauses.append(f"[{key}] = ?")
            params.append(value)

    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params
