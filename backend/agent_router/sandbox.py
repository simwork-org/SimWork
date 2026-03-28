"""Restricted pandas execution sandbox.

Allows LLM-generated pandas code to run against a pre-fetched DataFrame
with multiple security layers: static validation, restricted builtins,
thread-based timeout, and result extraction.
"""

from __future__ import annotations

import ast
import builtins
import re
import threading
from typing import Any

import numpy as np
import pandas as pd

# ── Static validation ────────────────────────────────────────────────

_FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"\b__import__\b", "__import__"),
    (r"\bimportlib\b", "importlib"),
    (r"\bopen\s*\(", "open()"),
    (r"\bexec\s*\(", "exec()"),
    (r"\beval\s*\(", "eval()"),
    (r"\bcompile\s*\(", "compile()"),
    (r"\b__builtins__\b", "__builtins__"),
    (r"\b__subclasses__\b", "__subclasses__"),
    (r"\b__globals__\b", "__globals__"),
    (r"\b__code__\b", "__code__"),
    (r"\bgetattr\s*\(", "getattr()"),
    (r"\bsetattr\s*\(", "setattr()"),
    (r"\bdelattr\s*\(", "delattr()"),
    (r"\bos\.", "os module"),
    (r"\bsys\.", "sys module"),
    (r"\bsubprocess\.", "subprocess module"),
    (r"\bshutil\.", "shutil module"),
    (r"\bsocket\.", "socket module"),
    (r"\bpathlib\.", "pathlib module"),
    (r"\.to_csv\b", "to_csv"),
    (r"\.to_excel\b", "to_excel"),
    (r"\.to_parquet\b", "to_parquet"),
    (r"\.to_sql\b", "to_sql"),
    (r"\.to_pickle\b", "to_pickle"),
    (r"\bread_csv\b", "read_csv"),
    (r"\bread_excel\b", "read_excel"),
    (r"\bread_sql\b", "read_sql"),
    (r"\bread_pickle\b", "read_pickle"),
]

_ALLOWED_IMPORT_ROOTS = {"pandas", "numpy"}


def _validate_imports(code: str) -> tuple[bool, str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"Syntax error: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in _ALLOWED_IMPORT_ROOTS:
                    return False, f"Forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root not in _ALLOWED_IMPORT_ROOTS:
                return False, f"Forbidden import: {module or 'relative import'}"
            if node.level:
                return False, "Relative imports are not allowed"

    return True, None


def validate_pandas_code(code: str) -> tuple[bool, str | None]:
    """Static validation of pandas code. Returns (is_valid, error_message)."""
    if not code or not code.strip():
        return False, "Empty code"

    imports_valid, import_error = _validate_imports(code)
    if not imports_valid:
        return False, import_error

    for pattern, description in _FORBIDDEN_PATTERNS:
        if re.search(pattern, code):
            return False, f"Forbidden pattern detected: {description}"

    return True, None


# ── Restricted execution ─────────────────────────────────────────────

_SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "sorted": sorted,
    "enumerate": enumerate,
    "zip": zip,
    "isinstance": isinstance,
    "print": lambda *a, **kw: None,  # silent no-op
    "True": True,
    "False": False,
    "None": None,
}


def _safe_import(name: str, globals: dict[str, Any] | None = None, locals: dict[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0):
    if level:
        raise ImportError("Relative imports are not allowed")

    root = name.split(".", 1)[0]
    if root not in _ALLOWED_IMPORT_ROOTS:
        raise ImportError(f"Import of '{name}' is not allowed")

    return builtins.__import__(name, globals, locals, fromlist, level)


_SAFE_BUILTINS["__import__"] = _safe_import


def execute_pandas_code(
    code: str,
    df: pd.DataFrame,
    timeout_seconds: int = 10,
    max_rows: int = 200,
) -> dict[str, Any]:
    """Execute pandas code in a restricted sandbox.

    The code receives `df` (a DataFrame) and must assign its final
    output to a variable called `result`.

    Returns dict with keys: ok, error, columns, rows, row_count, truncated.
    """
    # Layer 1: static validation
    is_valid, err = validate_pandas_code(code)
    if not is_valid:
        return {"ok": False, "error": f"Code validation failed: {err}"}

    # Layer 2: restricted globals
    exec_globals = {
        "__builtins__": _SAFE_BUILTINS,
        "pd": pd,
        "np": np,
        "df": df.copy(),  # isolate from caller
    }
    exec_locals: dict[str, Any] = {}

    # Layer 3: thread-based timeout
    exec_error: list[str] = []

    def _run():
        try:
            exec(code, exec_globals, exec_locals)  # noqa: S102
        except Exception as e:
            exec_error.append(f"{type(e).__name__}: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        return {"ok": False, "error": f"Execution timed out after {timeout_seconds}s"}

    if exec_error:
        return {"ok": False, "error": exec_error[0]}

    # Layer 4: result extraction
    result = exec_locals.get("result")
    if result is None:
        return {"ok": False, "error": "Code must assign output to a variable called `result`"}

    # Convert Series to DataFrame
    if isinstance(result, pd.Series):
        result = result.to_frame()

    if not isinstance(result, pd.DataFrame):
        return {"ok": False, "error": f"result must be a DataFrame, got {type(result).__name__}"}

    if result.empty:
        return {
            "ok": True,
            "columns": list(result.columns),
            "rows": [],
            "row_count": 0,
            "truncated": False,
        }

    truncated = len(result) > max_rows
    if truncated:
        result = result.head(max_rows)

    # Convert to list-of-dicts, handling NaN → None
    rows = result.where(result.notna(), None).to_dict(orient="records")

    return {
        "ok": True,
        "columns": list(result.columns),
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }
