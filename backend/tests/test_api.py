from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.simulation_engine.dependencies import get_engine


def _build_client(tmp_path: Path) -> TestClient:
    import os

    os.environ["SIMWORK_DB_PATH"] = str(tmp_path / "simwork-test.db")
    get_settings.cache_clear()
    get_engine.cache_clear()
    from backend.api.main import app

    return TestClient(app)


def test_session_flow(tmp_path: Path):
    client = _build_client(tmp_path)

    scenarios = client.get("/api/v1/scenarios")
    assert scenarios.status_code == 200
    assert scenarios.json()["scenarios"][0]["id"] == "checkout_conversion_drop"

    started = client.post(
        "/api/v1/sessions/start",
        json={"candidate_id": "candidate_123", "scenario_id": "checkout_conversion_drop"},
    )
    assert started.status_code == 200
    payload = started.json()
    session_id = payload["session_id"]
    assert payload["problem_statement"]

    query = client.post(
        f"/api/v1/sessions/{session_id}/query",
        json={"agent": "analyst", "query": "Show the checkout funnel conversion"},
    )
    assert query.status_code == 200
    assert query.json()["agent"] == "analyst"
    assert query.json()["data_visualization"]["type"] == "funnel"

    hypothesis = client.post(
        f"/api/v1/sessions/{session_id}/hypothesis",
        json={"hypothesis": "Payment service latency is affecting payment completion"},
    )
    assert hypothesis.status_code == 200
    assert hypothesis.json()["hypothesis_version"] == 1

    submit = client.post(
        f"/api/v1/sessions/{session_id}/submit",
        json={
            "root_cause": "Payment latency increase after gateway integration",
            "proposed_actions": ["Reduce latency", "Add retry flow"],
            "summary": "Latency growth caused payment failures and order loss.",
        },
    )
    assert submit.status_code == 200
    assert submit.json()["session_complete"] is True


def test_query_domain_violation(tmp_path: Path):
    client = _build_client(tmp_path)
    started = client.post(
        "/api/v1/sessions/start",
        json={"candidate_id": "candidate_123", "scenario_id": "checkout_conversion_drop"},
    ).json()
    session_id = started["session_id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/query",
        json={"agent": "analyst", "query": "Did usability feedback affect conversion?"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "query_domain_violation"
