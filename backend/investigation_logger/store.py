from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from backend.config import get_settings
from backend.models import AgentName, Visualization


class InvestigationStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_settings().db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    time_limit_minutes INTEGER NOT NULL,
                    current_hypothesis TEXT,
                    hypothesis_version INTEGER NOT NULL DEFAULT 0,
                    final_submission_json TEXT
                );

                CREATE TABLE IF NOT EXISTS query_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    agent_queried TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    response_generated TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    visualization_json TEXT
                );

                CREATE TABLE IF NOT EXISTS hypothesis_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    hypothesis_text TEXT NOT NULL,
                    hypothesis_version INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                );
                """
            )

    def create_session(
        self,
        session_id: str,
        candidate_id: str,
        scenario_id: str,
        time_limit_minutes: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (session_id, candidate_id, scenario_id, started_at, time_limit_minutes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, candidate_id, scenario_id, self._now(), time_limit_minutes),
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def log_query(
        self,
        session_id: str,
        candidate_id: str,
        agent: AgentName,
        query_text: str,
        response_text: str,
        visualization: Visualization | None,
    ) -> None:
        payload = visualization.model_dump() if visualization else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO query_logs (
                    session_id, candidate_id, agent_queried, query_text, response_generated, timestamp, visualization_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    candidate_id,
                    agent.value,
                    query_text,
                    response_text,
                    self._now(),
                    json.dumps(payload) if payload else None,
                ),
            )

    def list_queries(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, agent_queried, query_text, response_generated, visualization_json
                FROM query_logs
                WHERE session_id = ?
                ORDER BY timestamp ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
        queries: list[dict[str, Any]] = []
        for row in rows:
            visualization = json.loads(row["visualization_json"]) if row["visualization_json"] else None
            queries.append(
                {
                    "timestamp": row["timestamp"],
                    "agent": row["agent_queried"],
                    "query": row["query_text"],
                    "response": row["response_generated"],
                    "data_visualization": visualization,
                }
            )
        return queries

    def save_hypothesis(self, session_id: str, hypothesis_text: str) -> int:
        with self._connect() as connection:
            current = connection.execute(
                "SELECT hypothesis_version FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if current is None:
                raise KeyError(session_id)
            version = int(current["hypothesis_version"]) + 1
            timestamp = self._now()
            connection.execute(
                """
                UPDATE sessions
                SET current_hypothesis = ?, hypothesis_version = ?
                WHERE session_id = ?
                """,
                (hypothesis_text, version, session_id),
            )
            connection.execute(
                """
                INSERT INTO hypothesis_logs (session_id, hypothesis_text, hypothesis_version, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, hypothesis_text, version, timestamp),
            )
        return version

    def list_hypotheses(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT hypothesis_text, hypothesis_version, timestamp
                FROM hypothesis_logs
                WHERE session_id = ?
                ORDER BY hypothesis_version ASC
                """,
                (session_id,),
            ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "hypothesis": row["hypothesis_text"],
                "hypothesis_version": row["hypothesis_version"],
            }
            for row in rows
        ]

    def save_submission(self, session_id: str, submission: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE sessions
                SET completed_at = ?, final_submission_json = ?
                WHERE session_id = ?
                """,
                (self._now(), json.dumps(submission), session_id),
            )

    def get_status(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        started_at = datetime.fromisoformat(session["started_at"])
        completed_at = (
            datetime.fromisoformat(session["completed_at"]) if session.get("completed_at") else None
        )
        deadline = started_at + timedelta(minutes=int(session["time_limit_minutes"]))
        now = completed_at or datetime.now(UTC)
        time_remaining = max(0, int((deadline - now).total_seconds() // 60))
        queries_made = len(self.list_queries(session_id))
        return {
            "session_id": session["session_id"],
            "scenario_id": session["scenario_id"],
            "time_remaining_minutes": time_remaining,
            "current_hypothesis": session["current_hypothesis"],
            "queries_made": queries_made,
            "completed": completed_at is not None,
            "started_at": session["started_at"],
            "completed_at": session["completed_at"],
        }

    def get_final_submission(self, session_id: str) -> dict[str, Any] | None:
        session = self.get_session(session_id)
        if not session or not session.get("final_submission_json"):
            return None
        return json.loads(session["final_submission_json"])

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
