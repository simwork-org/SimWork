from __future__ import annotations

from agent_router.router import route_query
from data_layer.db import execute_authorized_select


class StubLLM:
    def __init__(self, json_responses=None, text_response: str | None = None):
        self.json_responses = list(json_responses or [])
        self.text_response = text_response
        self.calls: list[tuple[str, str, str]] = []

    def chat(self, system: str, user: str):
        self.calls.append(("chat", system, user))
        if not self.json_responses:
            raise RuntimeError("No more JSON responses queued")
        response = self.json_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def chat_text(self, system: str, user: str) -> str:
        self.calls.append(("chat_text", system, user))
        if self.text_response is None:
            raise RuntimeError("No text response queued")
        return self.text_response


def test_simple_question_can_be_answered_with_single_query():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Find the earliest customer signup.",
                "complexity": "single_query",
                "target_tables": ["users.csv"],
                "stop_condition": "Once the earliest signup row is found.",
                "next_steps": ["Ask for the earliest completed order too."],
            },
            {
                "action": "sql",
                "sql": "SELECT user_id, name, signup_date FROM [users] ORDER BY [signup_date] ASC",
                "title": "Earliest signed up users",
                "answer_mode": "table",
            },
        ],
        text_response="The earliest signup date belongs to the users shown in the attached result.",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Who is our first customer?")

    assert result["artifacts"]
    assert result["artifacts"][0]["kind"] == "table"
    assert result["citations"][0]["source"] == "users.csv"
    assert result["next_steps"] == ["Ask for the earliest completed order too."]
    assert "earliest signup" in result["response"].lower()


def test_agent_retries_after_invalid_query_and_then_succeeds():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Check payment failures after the migration.",
                "complexity": "multi_step",
                "target_tables": ["payments.csv", "orders.csv"],
                "stop_condition": "Once payment failures are tied to completed-order impact.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": "SELECT * FROM [paymentz]",
                "title": "Broken query",
                "answer_mode": "table",
            },
            {
                "action": "sql",
                "sql": (
                    "SELECT p.[status], COUNT(*) AS failed_count "
                    "FROM [payments] AS p "
                    "JOIN [orders] AS o ON p.[order_id] = o.[order_id] "
                    "GROUP BY p.[status] "
                    "ORDER BY failed_count DESC"
                ),
                "title": "Payment status breakdown",
                "answer_mode": "chart",
            },
        ],
        text_response="Failed payment statuses stand out clearly in the joined payment and order data.",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "What payment failures are affecting orders?")

    assert result["artifacts"]
    assert result["artifacts"][0]["kind"] == "chart"
    assert any("unauthorized table access" in warning.lower() or "no such table" in warning.lower() for warning in result["warnings"])
    assert "payments.csv" in result["citations"][0]["source"]
    assert "orders.csv" in result["citations"][0]["source"]


def test_agent_can_join_multiple_allowed_tables_within_role_scope():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Find the first customer who also placed the first completed order.",
                "complexity": "multi_step",
                "target_tables": ["users.csv", "orders.csv"],
                "stop_condition": "Once the earliest signup linked to the earliest completed order is identified.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": (
                    "SELECT u.[user_id], u.[name], u.[signup_date], o.[order_id], o.[created_at] "
                    "FROM [users] AS u "
                    "JOIN [orders] AS o ON u.[user_id] = o.[user_id] "
                    "WHERE o.[order_status] = 'completed' "
                    "ORDER BY u.[signup_date] ASC, o.[created_at] ASC"
                ),
                "title": "First customer with completed order",
                "answer_mode": "table",
            },
        ],
        text_response="The joined user and order data identifies the earliest signed-up customer who completed an order.",
    )

    result = route_query(
        llm,
        "checkout_conversion_drop",
        "analyst",
        "Who is the first customer who placed a completed order?",
    )

    assert result["artifacts"]
    assert result["artifacts"][0]["kind"] == "table"
    assert "users.csv" in result["citations"][0]["source"]
    assert "orders.csv" in result["citations"][0]["source"]


def test_agent_querying_other_roles_tables_fails_cleanly():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Look for support-ticket complaints.",
                "complexity": "single_query",
                "target_tables": ["orders.csv"],
                "stop_condition": "Stop when the ticket pattern is found.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": "SELECT * FROM [support_tickets]",
                "title": "Support tickets",
                "answer_mode": "table",
            },
        ],
        text_response="",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Show the latest support ticket complaints")

    assert result["artifacts"] == []
    assert any("unauthorized table access" in warning.lower() for warning in result["warnings"])


def test_shared_context_is_available_to_later_agent_turns():
    history = [
        {
            "agent": "engineering_lead",
            "query": "Did anything change in payments around January 10?",
            "response": "A RupeeFlow deployment appears around that date.",
            "artifacts": [{"title": "Deployment timeline"}],
            "citations": [{"title": "Deployments", "source": "deployments.csv"}],
        }
    ]
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Check whether order decline lines up with the engineering finding.",
                "complexity": "single_query",
                "target_tables": ["orders.csv"],
                "stop_condition": "Once order decline timing is confirmed.",
                "next_steps": [],
            },
            {
                "action": "finish",
                "reason": "Shared context already tells us the engineering clue to reference.",
                "title": "Final answer",
                "answer_mode": "text",
            },
        ],
        text_response="Order decline should be interpreted alongside the earlier engineering finding about a payment deployment.",
    )

    result = route_query(
        llm,
        "checkout_conversion_drop",
        "analyst",
        "Does the order drop line up with what engineering found?",
        conversation_history=history,
    )

    plan_user_payload = llm.calls[0][2]
    assert "engineering_lead" in plan_user_payload
    assert "payment deployment" in result["response"].lower()


def test_planner_receives_schema_and_sample_rows():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Inspect spending patterns.",
                "complexity": "single_query",
                "target_tables": ["orders.csv"],
                "stop_condition": "Once one valid row is found.",
                "next_steps": [],
            },
            {
                "action": "finish",
                "reason": "Schema context is enough for this test.",
                "title": "Final answer",
                "answer_mode": "text",
            },
        ],
        text_response="Using the available schema context.",
    )

    route_query(llm, "checkout_conversion_drop", "analyst", "Inspect spending patterns")

    planner_payload = llm.calls[0][2]
    assert '"schema"' in planner_payload
    assert '"sample_rows"' in planner_payload
    assert '"total_amount"' in planner_payload
    assert '"order_id"' in planner_payload


def test_scoped_sql_executor_rejects_unauthorized_tables():
    result = execute_authorized_select(
        scenario_id="checkout_conversion_drop",
        sql="SELECT * FROM [support_tickets]",
        allowed_tables={"orders", "payments", "users"},
        max_rows=5,
    )

    assert result["ok"] is False
    assert "unauthorized table access" in result["error"].lower()


def test_scoped_sql_executor_accepts_csv_style_table_names():
    result = execute_authorized_select(
        scenario_id="checkout_conversion_drop",
        sql="SELECT user_id, SUM(total_amount) AS total_spent FROM [orders.csv] GROUP BY user_id ORDER BY total_spent DESC",
        allowed_tables={"orders", "payments", "users"},
        max_rows=5,
    )

    assert result["ok"] is True
    assert result["referenced_tables"] == ["orders"]


def test_scoped_sql_executor_handles_trailing_semicolon_when_appending_limit():
    result = execute_authorized_select(
        scenario_id="checkout_conversion_drop",
        sql="SELECT user_id, total_amount FROM [orders];",
        allowed_tables={"orders", "payments", "users"},
        max_rows=5,
    )

    assert result["ok"] is True
    assert result["row_count"] == 5


def test_repeated_failed_attempts_end_with_bounded_failure_message():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Try to answer from invalid queries only.",
                "complexity": "multi_step",
                "target_tables": ["orders.csv"],
                "stop_condition": "Stop if nothing works.",
                "next_steps": [],
            },
            {"action": "sql", "sql": "SELECT * FROM [missing_one]", "title": "Attempt one", "answer_mode": "table"},
            {"action": "sql", "sql": "SELECT * FROM [missing_two]", "title": "Attempt two", "answer_mode": "table"},
            {"action": "sql", "sql": "SELECT * FROM [missing_three]", "title": "Attempt three", "answer_mode": "table"},
            {"action": "sql", "sql": "SELECT * FROM [missing_four]", "title": "Attempt four", "answer_mode": "table"},
        ],
        text_response="",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Keep trying broken queries")

    assert result["artifacts"] == []
    assert any("attempt limit" in warning.lower() for warning in result["warnings"])
    assert "attempt limit" in result["response"].lower()
