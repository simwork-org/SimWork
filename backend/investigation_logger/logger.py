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


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_query_log_columns(conn: sqlite3.Connection) -> None:
    wanted: dict[str, str] = {
        "artifacts_json": "TEXT",
        "citations_json": "TEXT",
        "warnings_json": "TEXT",
        "planner_json": "TEXT",
        "attempts_json": "TEXT",
    }
    existing = _table_columns(conn, "query_logs")
    for column, data_type in wanted.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE query_logs ADD COLUMN {column} {data_type}")


def _ensure_submissions_columns(conn: sqlite3.Connection) -> None:
    wanted: dict[str, str] = {
        "supporting_evidence_ids_json": "TEXT",
        "stakeholder_summary": "TEXT",
        "summary": "TEXT",
    }
    existing = _table_columns(conn, "submissions")
    for column, data_type in wanted.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE submissions ADD COLUMN {column} {data_type}")


def _ensure_sessions_columns(conn: sqlite3.Connection) -> None:
    wanted: dict[str, str] = {"challenge_id": "TEXT"}
    existing = _table_columns(conn, "sessions")
    for column, data_type in wanted.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} {data_type}")


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
            artifacts_json TEXT,
            citations_json TEXT,
            warnings_json TEXT,
            planner_json TEXT,
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
            summary TEXT,
            stakeholder_summary TEXT,
            supporting_evidence_ids_json TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS saved_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            query_log_id INTEGER NOT NULL,
            citation_id TEXT NOT NULL,
            agent TEXT NOT NULL,
            annotation TEXT,
            saved_at TEXT NOT NULL,
            UNIQUE(session_id, query_log_id, citation_id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id),
            FOREIGN KEY (query_log_id) REFERENCES query_logs(id)
        );

        CREATE TABLE IF NOT EXISTS session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_payload_json TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            sequence_number INTEGER NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS scoring_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            overall_score REAL,
            dimension_scores_json TEXT,
            process_signals_json TEXT,
            highlights_json TEXT,
            scored_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT,
            picture TEXT,
            created_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL
        );
        """
    )
    _ensure_query_log_columns(conn)
    _ensure_submissions_columns(conn)
    _ensure_sessions_columns(conn)
    conn.commit()
    conn.close()


def clear_all_session_data() -> None:
    """Remove all persisted session-scoped data."""
    conn = _get_conn()
    conn.executescript(
        """
        DELETE FROM scoring_results;
        DELETE FROM saved_evidence;
        DELETE FROM session_events;
        DELETE FROM submissions;
        DELETE FROM hypothesis_logs;
        DELETE FROM query_logs;
        DELETE FROM sessions;
        """
    )
    conn.commit()
    conn.close()


def upsert_user(user_id: str, email: str, name: str | None = None, picture: str | None = None) -> None:
    """Insert a new user or update last_login_at for an existing one."""
    conn = _get_conn()
    now = _utcnow()
    conn.execute(
        """
        INSERT INTO users (id, email, name, picture, created_at, last_login_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            email = excluded.email,
            name = excluded.name,
            picture = excluded.picture,
            last_login_at = excluded.last_login_at
        """,
        (user_id, email, name, picture, now, now),
    )
    conn.commit()
    conn.close()


def get_user(user_id: str) -> dict[str, Any] | None:
    """Get a user by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_user_sessions(user_id: str) -> list[dict[str, Any]]:
    """Get all sessions for a user."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT session_id, scenario_id, started_at, status FROM sessions WHERE candidate_id = ? ORDER BY started_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_session(session_id: str, candidate_id: str, scenario_id: str, challenge_id: str | None = None) -> None:
    conn = _get_conn()
    _ensure_sessions_columns(conn)
    conn.execute(
        "INSERT INTO sessions (session_id, candidate_id, scenario_id, challenge_id, started_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, candidate_id, scenario_id, challenge_id, _utcnow()),
    )
    conn.commit()
    conn.close()
    log_session_event(session_id, "session_started", {"scenario_id": scenario_id, "challenge_id": challenge_id})


def log_query(
    session_id: str,
    agent: str,
    query_text: str,
    response_text: str,
    artifacts: list[dict[str, Any]] | None = None,
    citations: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    planner: dict[str, Any] | None = None,
    attempts: list[dict[str, Any]] | None = None,
) -> int:
    conn = _get_conn()
    _ensure_query_log_columns(conn)
    cursor = conn.execute(
        """
        INSERT INTO query_logs (
            session_id,
            agent,
            query_text,
            response_text,
            artifacts_json,
            citations_json,
            warnings_json,
            planner_json,
            attempts_json,
            timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            agent,
            query_text,
            response_text,
            json.dumps(artifacts or []),
            json.dumps(citations or []),
            json.dumps(warnings or []),
            json.dumps(planner or {}),
            json.dumps(attempts or []),
            _utcnow(),
        ),
    )
    conn.commit()
    query_log_id = int(cursor.lastrowid)
    conn.close()
    return query_log_id


def log_session_event(session_id: str, event_type: str, event_payload: dict[str, Any] | None = None) -> int:
    conn = _get_conn()
    next_sequence = (
        conn.execute(
            "SELECT COALESCE(MAX(sequence_number), 0) + 1 AS next_sequence FROM session_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()["next_sequence"]
    )
    cursor = conn.execute(
        """
        INSERT INTO session_events (session_id, event_type, event_payload_json, timestamp, sequence_number)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, event_type, json.dumps(event_payload or {}), _utcnow(), next_sequence),
    )
    conn.commit()
    event_id = int(cursor.lastrowid)
    conn.close()
    return event_id


def get_session_events(session_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT id, event_type, event_payload_json, timestamp, sequence_number
        FROM session_events
        WHERE session_id = ?
        ORDER BY sequence_number
        """,
        (session_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "event_payload": json.loads(row["event_payload_json"] or "{}"),
            "timestamp": row["timestamp"],
            "sequence_number": row["sequence_number"],
        }
        for row in rows
    ]


def get_query_history(session_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    _ensure_query_log_columns(conn)
    rows = conn.execute(
        """
        SELECT id, agent, query_text, response_text, artifacts_json, citations_json, warnings_json, planner_json, attempts_json, timestamp
        FROM query_logs
        WHERE session_id = ?
        ORDER BY timestamp, id
        """,
        (session_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "query_log_id": r["id"],
            "agent": r["agent"],
            "query": r["query_text"],
            "response": r["response_text"],
            "artifacts": json.loads(r["artifacts_json"] or "[]"),
            "citations": json.loads(r["citations_json"] or "[]"),
            "warnings": json.loads(r["warnings_json"] or "[]"),
            "planner": json.loads(r["planner_json"] or "{}"),
            "attempts": json.loads(r["attempts_json"] or "[]"),
            "timestamp": r["timestamp"],
        }
        for r in rows
    ]


def get_query_log_detail(session_id: str, query_log_id: int) -> dict[str, Any] | None:
    """Return full query log detail including planner and attempts for a single query."""
    conn = _get_conn()
    _ensure_query_log_columns(conn)
    row = conn.execute(
        """
        SELECT id, agent, query_text, response_text, artifacts_json, citations_json,
               warnings_json, planner_json, attempts_json, timestamp
        FROM query_logs
        WHERE session_id = ? AND id = ?
        """,
        (session_id, query_log_id),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "query_log_id": row["id"],
        "agent": row["agent"],
        "query": row["query_text"],
        "response": row["response_text"],
        "artifacts": json.loads(row["artifacts_json"] or "[]"),
        "citations": json.loads(row["citations_json"] or "[]"),
        "warnings": json.loads(row["warnings_json"] or "[]"),
        "planner": json.loads(row["planner_json"] or "{}"),
        "attempts": json.loads(row["attempts_json"] or "[]"),
        "timestamp": row["timestamp"],
    }


def save_evidence(
    session_id: str,
    query_log_id: int,
    citation_id: str,
    agent: str,
    annotation: str | None = None,
) -> int:
    conn = _get_conn()
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO saved_evidence (session_id, query_log_id, citation_id, agent, annotation, saved_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, query_log_id, citation_id, agent, annotation, _utcnow()),
    )
    conn.commit()
    if cursor.lastrowid:
        saved_id = int(cursor.lastrowid)
    else:
        row = conn.execute(
            """
            SELECT id FROM saved_evidence
            WHERE session_id = ? AND query_log_id = ? AND citation_id = ?
            """,
            (session_id, query_log_id, citation_id),
        ).fetchone()
        saved_id = int(row["id"])
    conn.close()
    log_session_event(
        session_id,
        "artifact_saved",
        {"saved_evidence_id": saved_id, "query_log_id": query_log_id, "citation_id": citation_id, "agent": agent},
    )
    return saved_id


def remove_evidence(session_id: str, saved_evidence_id: int) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT query_log_id, citation_id, agent FROM saved_evidence WHERE id = ? AND session_id = ?",
        (saved_evidence_id, session_id),
    ).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute("DELETE FROM saved_evidence WHERE id = ? AND session_id = ?", (saved_evidence_id, session_id))
    conn.commit()
    conn.close()
    log_session_event(
        session_id,
        "artifact_removed",
        {
            "saved_evidence_id": saved_evidence_id,
            "query_log_id": row["query_log_id"],
            "citation_id": row["citation_id"],
            "agent": row["agent"],
        },
    )
    return True


def update_evidence_annotation(session_id: str, saved_evidence_id: int, annotation: str | None) -> bool:
    conn = _get_conn()
    cursor = conn.execute(
        "UPDATE saved_evidence SET annotation = ? WHERE id = ? AND session_id = ?",
        (annotation, saved_evidence_id, session_id),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    if updated:
        log_session_event(
            session_id,
            "artifact_annotation_updated",
            {"saved_evidence_id": saved_evidence_id, "annotation": annotation or ""},
        )
    return updated


def get_saved_evidence(session_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT id, query_log_id, citation_id, agent, annotation, saved_at
        FROM saved_evidence
        WHERE session_id = ?
        ORDER BY saved_at DESC, id DESC
        """,
        (session_id,),
    ).fetchall()
    query_rows = conn.execute(
        """
        SELECT id, query_text, artifacts_json, citations_json
        FROM query_logs
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchall()
    conn.close()

    query_lookup: dict[int, dict[str, Any]] = {}
    for row in query_rows:
        query_lookup[int(row["id"])] = {
            "query_text": row["query_text"],
            "artifacts": json.loads(row["artifacts_json"] or "[]"),
            "citations": json.loads(row["citations_json"] or "[]"),
        }

    resolved: list[dict[str, Any]] = []
    for row in rows:
        query_entry = query_lookup.get(int(row["query_log_id"]))
        if not query_entry:
            continue
        citation = next(
            (item for item in query_entry["citations"] if item.get("citation_id") == row["citation_id"]),
            None,
        )
        artifact = next(
            (
                item for item in query_entry["artifacts"]
                if row["citation_id"] in (item.get("citation_ids") or [])
            ),
            None,
        )
        if artifact is None or citation is None:
            continue
        resolved.append(
            {
                "id": row["id"],
                "query_log_id": row["query_log_id"],
                "citation_id": row["citation_id"],
                "agent": row["agent"],
                "artifact": artifact,
                "citation": citation,
                "annotation": row["annotation"],
                "query_text": query_entry["query_text"],
                "saved_at": row["saved_at"],
            }
        )
    return resolved


def submit_solution(
    session_id: str,
    root_cause: str,
    supporting_evidence_ids: list[int],
    proposed_actions: list[dict[str, Any]],
    stakeholder_summary: str,
) -> int:
    conn = _get_conn()
    _ensure_submissions_columns(conn)
    cursor = conn.execute(
        """
        INSERT INTO submissions (
            session_id,
            root_cause,
            proposed_actions,
            summary,
            stakeholder_summary,
            supporting_evidence_ids_json,
            timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            root_cause,
            json.dumps(proposed_actions),
            stakeholder_summary,
            stakeholder_summary,
            json.dumps(supporting_evidence_ids),
            _utcnow(),
        ),
    )
    conn.execute(
        "UPDATE sessions SET status = 'completed', ended_at = ? WHERE session_id = ?",
        (_utcnow(), session_id),
    )
    conn.commit()
    submission_id = int(cursor.lastrowid)
    conn.close()
    return submission_id


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


def get_submission(session_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    _ensure_submissions_columns(conn)
    row = conn.execute(
        "SELECT * FROM submissions WHERE session_id = ? ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "root_cause": row["root_cause"],
        "proposed_actions": json.loads(row["proposed_actions"] or "[]"),
        "stakeholder_summary": row["stakeholder_summary"] or row["summary"] or "",
        "supporting_evidence_ids": json.loads(row["supporting_evidence_ids_json"] or "[]"),
        "timestamp": row["timestamp"],
    }


def save_scoring_result(
    session_id: str,
    overall_score: float,
    dimension_scores: dict[str, Any],
    process_signals: dict[str, Any],
    highlights: dict[str, Any],
) -> int:
    conn = _get_conn()
    cursor = conn.execute(
        """
        INSERT INTO scoring_results (session_id, overall_score, dimension_scores_json, process_signals_json, highlights_json, scored_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            overall_score,
            json.dumps(dimension_scores),
            json.dumps(process_signals),
            json.dumps(highlights),
            _utcnow(),
        ),
    )
    conn.commit()
    result_id = int(cursor.lastrowid)
    conn.close()
    return result_id


def get_scoring_result(session_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM scoring_results WHERE session_id = ? ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "overall_score": row["overall_score"],
        "dimensions": json.loads(row["dimension_scores_json"] or "{}"),
        "process_signals": json.loads(row["process_signals_json"] or "{}"),
        **json.loads(row["highlights_json"] or "{}"),
        "scored_at": row["scored_at"],
    }
