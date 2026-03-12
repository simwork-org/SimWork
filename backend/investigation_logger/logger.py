"""Investigation logger — records candidate activity in SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "simwork.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            current_hypothesis TEXT,
            hypothesis_version INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            agent TEXT NOT NULL,
            query_text TEXT NOT NULL,
            response_text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS hypothesis_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            hypothesis TEXT NOT NULL,
            version INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            proposed_actions TEXT NOT NULL,
            summary TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
        """
    )
    conn.commit()
    conn.close()


def create_session(session_id: str, candidate_id: str, scenario_id: str) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO sessions (session_id, candidate_id, scenario_id, started_at) VALUES (?, ?, ?, ?)",
        (session_id, candidate_id, scenario_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def log_query(session_id: str, agent: str, query_text: str, response_text: str) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO query_logs (session_id, agent, query_text, response_text, timestamp) VALUES (?, ?, ?, ?, ?)",
        (session_id, agent, query_text, response_text, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def save_hypothesis(session_id: str, hypothesis: str) -> int:
    """Save hypothesis and return the new version number."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT hypothesis_version FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Session not found: {session_id}")
    new_version = row["hypothesis_version"] + 1
    conn.execute(
        "UPDATE sessions SET current_hypothesis = ?, hypothesis_version = ? WHERE session_id = ?",
        (hypothesis, new_version, session_id),
    )
    conn.execute(
        "INSERT INTO hypothesis_logs (session_id, hypothesis, version, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, hypothesis, new_version, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    return new_version


def get_query_history(session_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT agent, query_text, response_text, timestamp FROM query_logs WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "agent": r["agent"],
            "query": r["query_text"],
            "response": r["response_text"],
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def submit_solution(session_id: str, root_cause: str, proposed_actions: list[str], summary: str) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO submissions (session_id, root_cause, proposed_actions, summary, timestamp) VALUES (?, ?, ?, ?, ?)",
        (session_id, root_cause, json.dumps(proposed_actions), summary, datetime.now(timezone.utc).isoformat()),
    )
    conn.execute(
        "UPDATE sessions SET status = 'completed', ended_at = ? WHERE session_id = ?",
        (datetime.now(timezone.utc).isoformat(), session_id),
    )
    conn.commit()
    conn.close()


def get_session(session_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_queries_count(session_id: str) -> int:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM query_logs WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0
