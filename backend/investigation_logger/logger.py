"""Investigation logger — records candidate activity in PostgreSQL."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

APP_USERS_TABLE = "app_users"

_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://simwork:simwork@localhost:5432/simwork",
        )
        try:
            _pool = ThreadedConnectionPool(2, 20, db_url)
        except Exception:
            logger.error("Failed to create database connection pool — is PostgreSQL running?")
            raise
    return _pool


def _get_conn():
    return _get_pool().getconn()


def _put_conn(conn):
    _get_pool().putconn(conn)


def close_pool() -> None:
    """Close all connections in the pool (call on app shutdown)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def check_db() -> bool:
    """Return True if the database is reachable."""
    try:
        conn = _get_conn()
        try:
            conn.cursor().execute("SELECT 1")
            return True
        finally:
            _put_conn(conn)
    except Exception:
        return False


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                picture TEXT,
                role TEXT DEFAULT 'candidate',
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                challenge_id TEXT,
                assessment_id TEXT,
                invite_token TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                current_hypothesis TEXT,
                hypothesis_version INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                agent TEXT NOT NULL,
                query_text TEXT NOT NULL,
                response_text TEXT NOT NULL,
                artifacts_json TEXT,
                citations_json TEXT,
                warnings_json TEXT,
                planner_json TEXT,
                attempts_json TEXT,
                trace_json TEXT,
                llm_calls_json TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hypothesis_logs (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                hypothesis TEXT NOT NULL,
                version INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                root_cause TEXT NOT NULL,
                proposed_actions TEXT NOT NULL,
                summary TEXT,
                stakeholder_summary TEXT,
                supporting_evidence_ids_json TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS saved_evidence (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                query_log_id INTEGER NOT NULL REFERENCES query_logs(id),
                citation_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                annotation TEXT,
                saved_at TEXT NOT NULL,
                UNIQUE(session_id, query_log_id, citation_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_events (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                event_type TEXT NOT NULL,
                event_payload_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                sequence_number INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scoring_results (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                overall_score REAL,
                dimension_scores_json TEXT,
                process_signals_json TEXT,
                highlights_json TEXT,
                scored_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                owner_user_id TEXT NOT NULL UNIQUE REFERENCES app_users(id),
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                id TEXT PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES companies(id),
                scenario_id TEXT NOT NULL,
                challenge_id TEXT,
                title TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invite_tokens (
                token TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL REFERENCES assessments(id),
                candidate_email TEXT,
                created_at TEXT NOT NULL,
                used_at TEXT,
                used_by_user_id TEXT,
                expires_at TEXT
            )
        """)
        conn.commit()
    finally:
        _put_conn(conn)


def clear_all_session_data() -> None:
    """Remove all persisted session-scoped data."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM scoring_results")
        cur.execute("DELETE FROM saved_evidence")
        cur.execute("DELETE FROM session_events")
        cur.execute("DELETE FROM submissions")
        cur.execute("DELETE FROM hypothesis_logs")
        cur.execute("DELETE FROM query_logs")
        cur.execute("DELETE FROM sessions")
        conn.commit()
    finally:
        _put_conn(conn)


def upsert_user(
    user_id: str,
    email: str,
    name: str | None = None,
    picture: str | None = None,
    role: str | None = None,
) -> None:
    """Insert a new user or update last_login_at for an existing one.

    If *role* is provided and the user does not yet exist, the role is set.
    Existing users keep their current role (role is never overwritten on update).
    """
    conn = _get_conn()
    try:
        now = _utcnow()
        user_role = role or "candidate"
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO app_users (id, email, name, picture, role, created_at, last_login_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(id) DO UPDATE SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                picture = EXCLUDED.picture,
                last_login_at = EXCLUDED.last_login_at
            """,
            (user_id, email, name, picture, user_role, now, now),
        )
        conn.commit()
    finally:
        _put_conn(conn)


def set_user_role(user_id: str, role: str) -> None:
    """Explicitly update a user's role."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE app_users SET role = %s WHERE id = %s",
            (role, user_id),
        )
        conn.commit()
    finally:
        _put_conn(conn)


def get_user(user_id: str) -> dict[str, Any] | None:
    """Get a user by ID."""
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM app_users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _put_conn(conn)


def get_user_sessions(user_id: str) -> list[dict[str, Any]]:
    """Get all sessions for a user."""
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT
                s.session_id,
                s.scenario_id,
                s.challenge_id,
                s.assessment_id,
                s.invite_token,
                s.started_at,
                s.status,
                a.title AS assessment_title,
                c.name AS company_name
            FROM sessions s
            LEFT JOIN assessments a ON s.assessment_id = a.id
            LEFT JOIN companies c ON a.company_id = c.id
            WHERE s.candidate_id = %s
            ORDER BY s.started_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        _put_conn(conn)


def create_session(
    session_id: str,
    candidate_id: str,
    scenario_id: str,
    challenge_id: str | None = None,
    assessment_id: str | None = None,
    invite_token: str | None = None,
) -> None:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sessions (session_id, candidate_id, scenario_id, challenge_id, assessment_id, invite_token, started_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (session_id, candidate_id, scenario_id, challenge_id, assessment_id, invite_token, _utcnow()),
        )
        conn.commit()
    finally:
        _put_conn(conn)
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
    trace: dict[str, Any] | None = None,
    llm_calls: list[dict[str, Any]] | None = None,
) -> int:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO query_logs (
                session_id, agent, query_text, response_text,
                artifacts_json, citations_json, warnings_json,
                planner_json, attempts_json, trace_json,
                llm_calls_json, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
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
                json.dumps(trace or {}),
                json.dumps(llm_calls or []),
                _utcnow(),
            ),
        )
        query_log_id = cur.fetchone()[0]
        conn.commit()
        return int(query_log_id)
    finally:
        _put_conn(conn)


def log_session_event(
    session_id: str,
    event_type: str,
    event_payload: dict[str, Any] | None = None,
) -> int:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT COALESCE(MAX(sequence_number), 0) + 1 AS next_sequence FROM session_events WHERE session_id = %s",
            (session_id,),
        )
        next_sequence = cur.fetchone()["next_sequence"]
        cur.execute(
            """
            INSERT INTO session_events (session_id, event_type, event_payload_json, timestamp, sequence_number)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (session_id, event_type, json.dumps(event_payload or {}), _utcnow(), next_sequence),
        )
        event_id = cur.fetchone()["id"]
        conn.commit()
        return int(event_id)
    finally:
        _put_conn(conn)


def get_session_events(session_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, event_type, event_payload_json, timestamp, sequence_number
            FROM session_events
            WHERE session_id = %s
            ORDER BY sequence_number
            """,
            (session_id,),
        )
        rows = cur.fetchall()
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
    finally:
        _put_conn(conn)


def get_query_history(session_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, agent, query_text, response_text, artifacts_json, citations_json,
                   warnings_json, planner_json, attempts_json, timestamp
            FROM query_logs
            WHERE session_id = %s
            ORDER BY timestamp, id
            """,
            (session_id,),
        )
        rows = cur.fetchall()
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
    finally:
        _put_conn(conn)


def get_query_log_detail(session_id: str, query_log_id: int) -> dict[str, Any] | None:
    """Return full query log detail including planner and attempts for a single query."""
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, agent, query_text, response_text, artifacts_json, citations_json,
                   warnings_json, planner_json, attempts_json, trace_json, llm_calls_json, timestamp
            FROM query_logs
            WHERE session_id = %s AND id = %s
            """,
            (session_id, query_log_id),
        )
        row = cur.fetchone()
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
            "trace": json.loads(row["trace_json"] or "{}"),
            "llm_calls": json.loads(row["llm_calls_json"] or "[]"),
            "timestamp": row["timestamp"],
        }
    finally:
        _put_conn(conn)


def save_evidence(
    session_id: str,
    query_log_id: int,
    citation_id: str,
    agent: str,
    annotation: str | None = None,
) -> int:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO saved_evidence (session_id, query_log_id, citation_id, agent, annotation, saved_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id, query_log_id, citation_id) DO NOTHING
            RETURNING id
            """,
            (session_id, query_log_id, citation_id, agent, annotation, _utcnow()),
        )
        result = cur.fetchone()
        conn.commit()
        if result:
            saved_id = int(result["id"])
        else:
            cur.execute(
                """
                SELECT id FROM saved_evidence
                WHERE session_id = %s AND query_log_id = %s AND citation_id = %s
                """,
                (session_id, query_log_id, citation_id),
            )
            saved_id = int(cur.fetchone()["id"])
    finally:
        _put_conn(conn)
    log_session_event(
        session_id,
        "artifact_saved",
        {"saved_evidence_id": saved_id, "query_log_id": query_log_id, "citation_id": citation_id, "agent": agent},
    )
    return saved_id


def remove_evidence(session_id: str, saved_evidence_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT query_log_id, citation_id, agent FROM saved_evidence WHERE id = %s AND session_id = %s",
            (saved_evidence_id, session_id),
        )
        row = cur.fetchone()
        if row is None:
            return False
        cur.execute(
            "DELETE FROM saved_evidence WHERE id = %s AND session_id = %s",
            (saved_evidence_id, session_id),
        )
        conn.commit()
    finally:
        _put_conn(conn)
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
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE saved_evidence SET annotation = %s WHERE id = %s AND session_id = %s",
            (annotation, saved_evidence_id, session_id),
        )
        conn.commit()
        updated = cur.rowcount > 0
    finally:
        _put_conn(conn)
    if updated:
        log_session_event(
            session_id,
            "artifact_annotation_updated",
            {"saved_evidence_id": saved_evidence_id, "annotation": annotation or ""},
        )
    return updated


def get_saved_evidence(session_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, query_log_id, citation_id, agent, annotation, saved_at
            FROM saved_evidence
            WHERE session_id = %s
            ORDER BY saved_at DESC, id DESC
            """,
            (session_id,),
        )
        rows = cur.fetchall()
        cur.execute(
            """
            SELECT id, query_text, artifacts_json, citations_json
            FROM query_logs
            WHERE session_id = %s
            """,
            (session_id,),
        )
        query_rows = cur.fetchall()
    finally:
        _put_conn(conn)

    query_lookup: dict[int, dict[str, Any]] = {}
    for qr in query_rows:
        query_lookup[int(qr["id"])] = {
            "query_text": qr["query_text"],
            "artifacts": json.loads(qr["artifacts_json"] or "[]"),
            "citations": json.loads(qr["citations_json"] or "[]"),
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
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO submissions (
                session_id, root_cause, proposed_actions, summary,
                stakeholder_summary, supporting_evidence_ids_json, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
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
        submission_id = cur.fetchone()[0]
        cur.execute(
            "UPDATE sessions SET status = 'completed', ended_at = %s WHERE session_id = %s",
            (_utcnow(), session_id),
        )
        conn.commit()
        return int(submission_id)
    finally:
        _put_conn(conn)


def get_session(session_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM sessions WHERE session_id = %s", (session_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _put_conn(conn)


def get_queries_count(session_id: str) -> int:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM query_logs WHERE session_id = %s",
            (session_id,),
        )
        row = cur.fetchone()
        return row["cnt"] if row else 0
    finally:
        _put_conn(conn)


def get_submission(session_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM submissions WHERE session_id = %s ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        row = cur.fetchone()
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
    finally:
        _put_conn(conn)


def save_scoring_result(
    session_id: str,
    overall_score: float,
    dimension_scores: dict[str, Any],
    process_signals: dict[str, Any],
    highlights: dict[str, Any],
) -> int:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO scoring_results (session_id, overall_score, dimension_scores_json, process_signals_json, highlights_json, scored_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
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
        result_id = cur.fetchone()[0]
        conn.commit()
        return int(result_id)
    finally:
        _put_conn(conn)


def get_scoring_result(session_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM scoring_results WHERE session_id = %s ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "overall_score": row["overall_score"],
            "dimensions": json.loads(row["dimension_scores_json"] or "{}"),
            "process_signals": json.loads(row["process_signals_json"] or "{}"),
            **json.loads(row["highlights_json"] or "{}"),
            "scored_at": row["scored_at"],
        }
    finally:
        _put_conn(conn)


# ── Company / Assessment / Invite helpers ──


def create_company(name: str, owner_user_id: str) -> int:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO companies (name, owner_user_id, created_at) VALUES (%s, %s, %s) RETURNING id",
            (name, owner_user_id, _utcnow()),
        )
        company_id = cur.fetchone()[0]
        conn.commit()
        return int(company_id)
    finally:
        _put_conn(conn)


def get_company_by_owner(owner_user_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM companies WHERE owner_user_id = %s", (owner_user_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _put_conn(conn)


def create_assessment(
    assessment_id: str,
    company_id: int,
    scenario_id: str,
    challenge_id: str | None = None,
    title: str | None = None,
) -> None:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO assessments (id, company_id, scenario_id, challenge_id, title, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (assessment_id, company_id, scenario_id, challenge_id, title, _utcnow()),
        )
        conn.commit()
    finally:
        _put_conn(conn)


def get_assessments_by_company(company_id: int) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM assessments WHERE company_id = %s ORDER BY created_at DESC",
            (company_id,),
        )
        rows = cur.fetchall()
        results = []
        for row in rows:
            assessment = dict(row)
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active
                FROM sessions WHERE assessment_id = %s
                """,
                (row["id"],),
            )
            counts = cur.fetchone()
            assessment["candidate_total"] = counts["total"] if counts else 0
            assessment["candidate_completed"] = int(counts["completed"] or 0) if counts else 0
            assessment["candidate_active"] = int(counts["active"] or 0) if counts else 0
            results.append(assessment)
        return results
    finally:
        _put_conn(conn)


def get_assessment(assessment_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM assessments WHERE id = %s", (assessment_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _put_conn(conn)


def get_assessment_candidates(assessment_id: str) -> list[dict[str, Any]]:
    """Return sessions + user info + scores for all candidates in an assessment."""
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT s.session_id, s.candidate_id, s.started_at, s.ended_at, s.status,
                   u.email, u.name, u.picture,
                   sr.overall_score, sr.scored_at
            FROM sessions s
            LEFT JOIN app_users u ON s.candidate_id = u.id
            LEFT JOIN scoring_results sr ON s.session_id = sr.session_id
            WHERE s.assessment_id = %s
            ORDER BY s.started_at DESC
            """,
            (assessment_id,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        _put_conn(conn)


def create_invite_token(
    token: str,
    assessment_id: str,
    candidate_email: str | None = None,
    expires_at: str | None = None,
) -> None:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO invite_tokens (token, assessment_id, candidate_email, created_at, expires_at) VALUES (%s, %s, %s, %s, %s)",
            (token, assessment_id, candidate_email, _utcnow(), expires_at),
        )
        conn.commit()
    finally:
        _put_conn(conn)


def get_invite_token(token: str) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT it.*, a.scenario_id, a.challenge_id, a.title AS assessment_title,
                   c.name AS company_name, c.id AS company_id
            FROM invite_tokens it
            JOIN assessments a ON it.assessment_id = a.id
            JOIN companies c ON a.company_id = c.id
            WHERE it.token = %s
            """,
            (token,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _put_conn(conn)


def claim_invite_token(token: str, user_id: str) -> None:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE invite_tokens SET used_at = %s, used_by_user_id = %s WHERE token = %s",
            (_utcnow(), user_id, token),
        )
        conn.commit()
    finally:
        _put_conn(conn)


def get_invite_tokens_by_assessment(assessment_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT it.token, it.candidate_email, it.created_at, it.used_at, it.used_by_user_id, it.expires_at,
                   u.email AS claimed_by_email, u.name AS claimed_by_name
            FROM invite_tokens it
            LEFT JOIN app_users u ON it.used_by_user_id = u.id
            WHERE it.assessment_id = %s
            ORDER BY it.created_at DESC
            """,
            (assessment_id,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        _put_conn(conn)
