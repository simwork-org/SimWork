"""SQLite data layer — single connection per scenario, query helpers."""

from __future__ import annotations

import re
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
                f"Database not found: {path}. Run the scenario generator to create scenario.db."
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


def query_with_columns(
    scenario_id: str,
    sql: str,
    params: tuple | list = (),
) -> tuple[list[str], list[dict[str, Any]]]:
    """Execute a SQL query and return columns with rows."""
    conn = get_connection(scenario_id)
    cursor = conn.execute(sql, params)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return columns, rows


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


def get_distinct_value_previews(
    scenario_id: str,
    table: str,
    *,
    max_unique: int = 12,
    max_values: int = 8,
) -> list[dict[str, Any]]:
    """Return low-cardinality distinct values for likely categorical columns."""
    previews: list[dict[str, Any]] = []
    for column in get_table_schema(scenario_id, table):
        column_name = column["name"]
        column_type = (column["type"] or "").upper()
        if any(token in column_type for token in ("INT", "REAL", "NUM", "DEC", "FLOAT", "DOUBLE")):
            continue

        distinct_count = query_value(
            scenario_id,
            f"SELECT COUNT(DISTINCT [{column_name}]) FROM [{table}] WHERE [{column_name}] IS NOT NULL",
        )
        if not distinct_count or distinct_count > max_unique:
            continue

        values = query(
            scenario_id,
            (
                f"SELECT [{column_name}] AS value, COUNT(*) AS count "
                f"FROM [{table}] "
                f"WHERE [{column_name}] IS NOT NULL "
                f"GROUP BY [{column_name}] "
                f"ORDER BY count DESC, [{column_name}] ASC "
                f"LIMIT ?"
            ),
            (max_values,),
        )
        previews.append(
            {
                "column": column_name,
                "distinct_count": int(distinct_count),
                "values": values,
            }
        )
    return previews


def get_table_date_ranges(scenario_id: str, table: str) -> list[dict[str, str]]:
    """Return min/max values for date-like columns in a table."""
    ranges: list[dict[str, str]] = []
    for column in get_table_schema(scenario_id, table):
        column_name = column["name"]
        lowered = column_name.lower()
        if not any(token in lowered for token in ("date", "time", "timestamp", "_at")):
            continue
        min_value = query_value(scenario_id, f"SELECT MIN([{column_name}]) FROM [{table}] WHERE [{column_name}] IS NOT NULL")
        max_value = query_value(scenario_id, f"SELECT MAX([{column_name}]) FROM [{table}] WHERE [{column_name}] IS NOT NULL")
        if min_value is None or max_value is None:
            continue
        ranges.append(
            {
                "column": column_name,
                "min": str(min_value),
                "max": str(max_value),
            }
        )
    return ranges


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


READ_ONLY_SQL_PREFIXES = ("select", "with")
FORBIDDEN_SQL_TOKENS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "attach",
    "detach",
    "pragma",
    "vacuum",
)


def extract_referenced_tables(sql: str) -> set[str]:
    """Extract likely table names from FROM/JOIN clauses."""
    cleaned = re.sub(r"--.*?$|/\*.*?\*/", " ", sql, flags=re.MULTILINE | re.DOTALL)
    refs = set()
    for match in re.finditer(r"\b(?:from|join)\s+([^\s,()]+)", cleaned, flags=re.IGNORECASE):
        token = match.group(1).strip()
        token = token.strip("[]\"`;")
        if "." in token:
            token = token.split(".")[-1]
        lowered = token.lower()
        if lowered in {"select"}:
            continue
        refs.add(token)
    return refs


def validate_select_sql(sql: str, allowed_tables: set[str]) -> tuple[bool, str | None, set[str]]:
    """Validate that SQL is read-only and references only allowed tables."""
    stripped = sql.strip()
    lowered = stripped.lower()
    if not stripped:
        return False, "Query is empty.", set()
    if not lowered.startswith(READ_ONLY_SQL_PREFIXES):
        return False, "Only read-only SELECT queries are allowed.", set()
    if ";" in stripped.rstrip(";"):
        return False, "Only a single SQL statement is allowed.", set()
    tokenized = re.findall(r"\b[a-z_]+\b", lowered)
    for token in FORBIDDEN_SQL_TOKENS:
        if token in tokenized:
            return False, f"Forbidden SQL keyword detected: {token}.", set()

    referenced = extract_referenced_tables(stripped)
    unauthorized = {table for table in referenced if table not in allowed_tables}
    if unauthorized:
        return False, f"Unauthorized table access: {', '.join(sorted(unauthorized))}.", referenced
    return True, None, referenced


def ensure_limit(sql: str, max_rows: int) -> str:
    """Append a LIMIT when the query does not already specify one."""
    stripped = sql.strip().rstrip(";").rstrip()
    if re.search(r"\blimit\s+\d+\b", stripped, flags=re.IGNORECASE):
        return stripped
    return f"{stripped} LIMIT {max_rows}"
def execute_authorized_select(
    scenario_id: str,
    sql: str,
    allowed_tables: set[str],
    max_rows: int = 50,
) -> dict[str, Any]:
    """Validate and execute a read-only query within the caller's table scope."""
    valid, error, referenced_tables = validate_select_sql(sql, allowed_tables)
    if not valid:
        return {
            "ok": False,
            "error": error,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "referenced_tables": sorted(referenced_tables),
            "truncated": False,
            "executed_sql": sql,
        }

    limited_sql = ensure_limit(sql, max_rows + 1)
    try:
        columns, rows = query_with_columns(scenario_id, limited_sql)
    except sqlite3.Error as exc:
        return {
            "ok": False,
            "error": str(exc),
            "columns": [],
            "rows": [],
            "row_count": 0,
            "referenced_tables": sorted(referenced_tables),
            "truncated": False,
            "executed_sql": limited_sql,
        }

    truncated = len(rows) > max_rows
    visible_rows = rows[:max_rows]
    return {
        "ok": True,
        "error": None,
        "columns": columns,
        "rows": visible_rows,
        "row_count": len(visible_rows),
        "referenced_tables": sorted(referenced_tables),
        "truncated": truncated,
        "executed_sql": limited_sql,
    }
