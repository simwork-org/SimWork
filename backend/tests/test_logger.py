from __future__ import annotations

from investigation_logger import logger


def test_query_history_persists_query_log_id_and_metadata(tmp_path, monkeypatch):
    test_db = tmp_path / "simwork-test.db"
    monkeypatch.setattr(logger, "DB_PATH", test_db)

    logger.init_db()
    logger.create_session("session_test", "candidate_1", "checkout_conversion_drop")
    query_log_id = logger.log_query(
        session_id="session_test",
        agent="analyst",
        query_text="Show daily order trends",
        response_text="Orders declined over time.",
        artifacts=[
            {
                "kind": "chart",
                "title": "Daily order trend",
                "chart_type": "line",
                "labels": ["2025-01-01", "2025-01-02"],
                "series": [{"name": "orders", "values": [10, 8]}],
                "citation_ids": ["ev_123"],
            }
        ],
        citations=[
            {
                "citation_id": "ev_123",
                "source": "orders",
                "title": "Daily order trend",
                "summary": "Computed daily order counts from orders.",
            }
        ],
        warnings=["Planner fallback used due to invalid planner output."],
        planner={"intent": "trend", "answer_mode": "chart"},
    )

    history = logger.get_query_history("session_test")

    assert len(history) == 1
    assert history[0]["query_log_id"] == query_log_id
    assert history[0]["artifacts"][0]["kind"] == "chart"
    assert history[0]["citations"][0]["source"] == "orders"
    assert history[0]["warnings"] == ["Planner fallback used due to invalid planner output."]
    assert history[0]["planner"]["intent"] == "trend"


def test_saved_evidence_and_session_events_are_persisted(tmp_path, monkeypatch):
    test_db = tmp_path / "simwork-test.db"
    monkeypatch.setattr(logger, "DB_PATH", test_db)

    logger.init_db()
    logger.create_session("session_test", "candidate_1", "checkout_conversion_drop")
    query_log_id = logger.log_query(
        session_id="session_test",
        agent="analyst",
        query_text="Show daily order trends",
        response_text="Orders declined over time.",
        artifacts=[
            {
                "kind": "chart",
                "title": "Daily order trend",
                "chart_type": "line",
                "labels": ["2025-01-01", "2025-01-02"],
                "series": [{"name": "orders", "values": [10, 8]}],
                "citation_ids": ["ev_123"],
            }
        ],
        citations=[
            {
                "citation_id": "ev_123",
                "source": "orders",
                "title": "Daily order trend",
                "summary": "Computed daily order counts from orders.",
            }
        ],
        warnings=[],
        planner={"intent": "trend", "answer_mode": "chart"},
    )

    saved_id = logger.save_evidence("session_test", query_log_id, "ev_123", "analyst", "This shows the drop clearly.")
    saved_items = logger.get_saved_evidence("session_test")
    assert len(saved_items) == 1
    assert saved_items[0]["id"] == saved_id
    assert saved_items[0]["artifact"]["title"] == "Daily order trend"
    assert saved_items[0]["annotation"] == "This shows the drop clearly."

    updated = logger.update_evidence_annotation("session_test", saved_id, "Updated annotation.")
    assert updated is True
    assert logger.get_saved_evidence("session_test")[0]["annotation"] == "Updated annotation."

    removed = logger.remove_evidence("session_test", saved_id)
    assert removed is True
    assert logger.get_saved_evidence("session_test") == []

    events = logger.get_session_events("session_test")
    assert [event["event_type"] for event in events] == [
        "session_started",
        "artifact_saved",
        "artifact_annotation_updated",
        "artifact_removed",
    ]
    assert [event["sequence_number"] for event in events] == [1, 2, 3, 4]


def test_clear_all_session_data_removes_previous_sessions(tmp_path, monkeypatch):
    test_db = tmp_path / "simwork-test.db"
    monkeypatch.setattr(logger, "DB_PATH", test_db)

    logger.init_db()
    logger.create_session("session_one", "candidate_1", "checkout_conversion_drop")
    logger.log_query(
        session_id="session_one",
        agent="analyst",
        query_text="Show daily order trends",
        response_text="Orders declined over time.",
        artifacts=[],
        citations=[],
        warnings=[],
        planner={},
    )

    logger.clear_all_session_data()

    assert logger.get_session("session_one") is None
    assert logger.get_query_history("session_one") == []
    assert logger.get_session_events("session_one") == []
