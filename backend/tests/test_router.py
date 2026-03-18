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
                "target_tables": ["users"],
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
    assert result["citations"][0]["source"] == "users"
    assert result["next_steps"] == ["Ask for the earliest completed order too."]
    assert "earliest signup date" in result["response"].lower()


def test_agent_retries_after_invalid_query_and_then_succeeds():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Check payment failures after the migration.",
                "complexity": "multi_step",
                "target_tables": ["payments", "orders"],
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
    assert "payments" in result["citations"][0]["source"]
    assert "orders" in result["citations"][0]["source"]


def test_agent_can_join_multiple_allowed_tables_within_role_scope():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Find the first customer who also placed the first completed order.",
                "complexity": "multi_step",
                "target_tables": ["users", "orders"],
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
    assert "users" in result["citations"][0]["source"]
    assert "orders" in result["citations"][0]["source"]


def test_table_answer_mode_stays_table_and_response_uses_real_rows():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Show month-over-month order volume in tabular form.",
                "complexity": "single_query",
                "target_tables": ["orders"],
                "stop_condition": "Once the monthly table is available.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": (
                    "SELECT strftime('%Y-%m', created_at) AS month, COUNT(order_id) AS order_count "
                    "FROM [orders] "
                    "GROUP BY strftime('%Y-%m', created_at) "
                    "ORDER BY month"
                ),
                "title": "Monthly order volume",
                "answer_mode": "table",
            },
        ],
        text_response="Monthly order volume shows consistent trends across the period.",
    )

    result = route_query(
        llm,
        "checkout_conversion_drop",
        "analyst",
        "give month on month change in order volume in tabular form",
    )

    assert result["artifacts"][0]["kind"] == "table"
    assert "monthly order volume" in result["response"].lower()


def test_agent_querying_other_roles_tables_fails_cleanly():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Look for support-ticket complaints.",
                "complexity": "single_query",
                "target_tables": ["orders"],
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


def test_conversation_context_is_available_to_later_agent_turns():
    history = [
        {
            "agent": "engineering_lead",
            "query": "Did anything change in payments around January 10?",
            "response": "A RupeeFlow deployment appears around that date.",
            "artifacts": [{"title": "Deployment timeline"}],
            "citations": [{"title": "Deployments", "source": "deployments"}],
            "attempts": [],
        }
    ]
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Check whether order decline lines up with the engineering finding.",
                "complexity": "single_query",
                "target_tables": ["orders"],
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
                "target_tables": ["orders"],
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
    assert '"distinct_value_previews"' in planner_payload
    assert '"total_amount"' in planner_payload
    assert '"order_id"' in planner_payload


def test_planner_receives_distinct_user_type_values():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Trend orders for power users.",
                "complexity": "single_query",
                "target_tables": ["users", "orders"],
                "stop_condition": "Once the filtered trend query is prepared.",
                "next_steps": [],
            },
            {
                "action": "finish",
                "reason": "This test only validates metadata context.",
                "title": "Final answer",
                "answer_mode": "text",
            },
        ],
        text_response="Using the users.user_type metadata.",
    )

    route_query(llm, "checkout_conversion_drop", "analyst", "plot the trend of orders placed by power users")

    planner_payload = llm.calls[0][2]
    assert '"user_type"' in planner_payload
    assert '"power"' in planner_payload


def test_planner_receives_table_date_ranges():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Show the full daily order trend.",
                "complexity": "single_query",
                "target_tables": ["orders"],
                "stop_condition": "Once the full time series is available.",
                "next_steps": [],
            },
            {
                "action": "finish",
                "reason": "This test only validates date-range metadata.",
                "title": "Final answer",
                "answer_mode": "text",
            },
        ],
        text_response="Using the full available order date range.",
    )

    route_query(llm, "checkout_conversion_drop", "analyst", "Show daily order trends")

    planner_payload = llm.calls[0][2]
    assert '"date_ranges"' in planner_payload
    assert '"created_at"' in planner_payload
    assert '"2024-10-01' in planner_payload
    assert '"2025-03-31' in planner_payload


def test_ambiguous_question_returns_single_clarifying_question():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Determine what the user means by most valuable customer.",
                "complexity": "single_query",
                "target_tables": ["orders", "users"],
                "stop_condition": "Clarify the metric first.",
                "next_steps": [],
                "needs_clarification": True,
                "clarification_reason": "I need to know which metric should define customer value before I rank customers.",
                "pending_follow_up": {
                    "prompt": "How should I define most valuable customer?",
                    "choices": ["Highest total spend", "Highest order frequency", "Highest average order value"],
                    "default_choice": "Highest total spend",
                    "resolved_query_template": "{original_question} by {choice}",
                    "allow_free_text": True,
                },
            }
        ],
        text_response="",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "most valuable customer")

    assert result["artifacts"] == []
    assert result["pending_follow_up"] is not None
    assert result["pending_follow_up"]["prompt"] == "How should I define most valuable customer?"
    assert "highest total spend" in result["response"].lower()


def test_choice_based_clarification_reply_resumes_investigation():
    history = [
        {
            "agent": "analyst",
            "query": "most valuable customer",
            "response": "How should I define most valuable customer?",
            "artifacts": [],
            "citations": [],
            "warnings": [],
            "planner": {
                "original_query": "most valuable customer",
                "effective_query": "most valuable customer",
                "pending_follow_up": {
                    "prompt": "How should I define most valuable customer?",
                    "choices": ["Highest total spend", "Highest order frequency"],
                    "default_choice": "Highest total spend",
                    "resolved_query_template": "{original_question} by {choice}",
                    "allow_free_text": True,
                },
                "clarification_count": 1,
                "clarification_history": [],
            },
        }
    ]
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Rank customers by total spend.",
                "complexity": "single_query",
                "target_tables": ["orders"],
                "stop_condition": "Once the top spender is found.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": (
                    "SELECT user_id, SUM(total_amount) AS total_spent "
                    "FROM [orders] "
                    "GROUP BY user_id "
                    "ORDER BY total_spent DESC"
                ),
                "title": "Top customer by spend",
                "answer_mode": "metric",
            },
        ],
        text_response="The top customer by total spend is shown in the result.",
    )

    result = route_query(
        llm,
        "checkout_conversion_drop",
        "analyst",
        "Highest total spend",
        conversation_history=history,
    )

    planner_payload = llm.calls[0][2]
    assert "most valuable customer by Highest total spend" in planner_payload
    assert result["pending_follow_up"] is None
    assert result["artifacts"]


def test_free_text_clarification_reply_resumes_investigation():
    history = [
        {
            "agent": "analyst",
            "query": "most valuable customer",
            "response": "How should I define most valuable customer?",
            "artifacts": [],
            "citations": [],
            "warnings": [],
            "planner": {
                "original_query": "most valuable customer",
                "effective_query": "most valuable customer",
                "pending_follow_up": {
                    "prompt": "How should I define most valuable customer?",
                    "choices": ["Highest total spend", "Highest order frequency"],
                    "default_choice": "Highest total spend",
                    "resolved_query_template": "{original_question} with metric {choice}",
                    "allow_free_text": True,
                },
                "clarification_count": 1,
                "clarification_history": [],
            },
        }
    ]
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Rank customers by spend on completed orders only.",
                "complexity": "single_query",
                "target_tables": ["orders"],
                "stop_condition": "Once the top spender is found.",
                "next_steps": [],
            },
            {
                "action": "finish",
                "reason": "This test only validates free-text clarification propagation.",
                "title": "Final answer",
                "answer_mode": "text",
            },
        ],
        text_response="Using the user's clarification about completed-order spending.",
    )

    result = route_query(
        llm,
        "checkout_conversion_drop",
        "analyst",
        "total spend on completed orders only",
        conversation_history=history,
    )

    planner_payload = llm.calls[0][2]
    assert "total spend on completed orders only" in planner_payload
    assert any("free-text clarification" in warning.lower() for warning in result["warnings"])


def test_agent_can_ask_second_clarifying_question_if_needed():
    history = [
        {
            "agent": "analyst",
            "query": "most valuable customer",
            "response": "How should I define most valuable customer?",
            "artifacts": [],
            "citations": [],
            "warnings": [],
            "planner": {
                "original_query": "most valuable customer",
                "effective_query": "most valuable customer",
                "pending_follow_up": {
                    "prompt": "How should I define most valuable customer?",
                    "choices": ["Highest total spend", "Highest order frequency"],
                    "default_choice": "Highest total spend",
                    "resolved_query_template": "{original_question} by {choice}",
                    "allow_free_text": True,
                },
                "clarification_count": 1,
                "clarification_history": [],
            },
        }
    ]
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Need to know whether to include cancelled orders.",
                "complexity": "single_query",
                "target_tables": ["orders"],
                "stop_condition": "Clarify order status scope.",
                "next_steps": [],
                "needs_clarification": True,
                "clarification_reason": "I still need to know whether to include only completed orders or all orders.",
                "pending_follow_up": {
                    "prompt": "Should I use only completed orders or all orders?",
                    "choices": ["Completed orders only", "All orders"],
                    "default_choice": "Completed orders only",
                    "resolved_query_template": "{original_question} using {choice}",
                    "allow_free_text": True,
                },
            }
        ],
        text_response="",
    )

    result = route_query(
        llm,
        "checkout_conversion_drop",
        "analyst",
        "Highest total spend",
        conversation_history=history,
    )

    assert result["pending_follow_up"] is not None
    assert result["_planner"]["clarification_count"] == 2
    assert "completed orders" in result["response"].lower()


def test_agent_stops_asking_after_clarification_cap():
    history = [
        {
            "agent": "analyst",
            "query": "most valuable customer",
            "response": "Previous clarification",
            "artifacts": [],
            "citations": [],
            "warnings": [],
            "planner": {
                "original_query": "most valuable customer",
                "effective_query": "most valuable customer using total spend",
                "pending_follow_up": {
                    "prompt": "Another clarification?",
                    "choices": ["Yes", "No"],
                    "default_choice": "Yes",
                    "resolved_query_template": "{original_question} with {choice}",
                    "allow_free_text": True,
                },
                "clarification_count": 3,
                "clarification_history": [{"prompt": "q1", "answer": "a1"}, {"prompt": "q2", "answer": "a2"}, {"prompt": "q3", "answer": "a3"}],
            },
        }
    ]
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Still asks for clarification, but should be blocked by cap.",
                "complexity": "single_query",
                "target_tables": ["orders"],
                "stop_condition": "Proceed with the best interpretation.",
                "next_steps": [],
                "needs_clarification": True,
                "clarification_reason": "Another clarification would normally help.",
                "pending_follow_up": {
                    "prompt": "Should I include only completed orders?",
                    "choices": ["Yes", "No"],
                    "default_choice": "Yes",
                    "resolved_query_template": "{original_question} using {choice}",
                    "allow_free_text": True,
                },
            },
            {
                "action": "finish",
                "reason": "Proceed with the best interpretation after the clarification cap.",
                "title": "Final answer",
                "answer_mode": "text",
            },
        ],
        text_response="The clarification limit was reached, so I proceeded with the best available interpretation.",
    )

    result = route_query(
        llm,
        "checkout_conversion_drop",
        "analyst",
        "yes",
        conversation_history=history,
    )

    assert result["pending_follow_up"] is None
    assert any("clarification limit reached" in warning.lower() for warning in result["warnings"])


def test_chart_queries_can_return_more_than_twelve_rows():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Plot the daily order trend.",
                "complexity": "single_query",
                "target_tables": ["orders"],
                "stop_condition": "Once the daily order trend is available.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": (
                    "SELECT substr(created_at, 1, 10) AS order_date, COUNT(*) AS order_count "
                    "FROM [orders] "
                    "GROUP BY order_date "
                    "ORDER BY order_date"
                ),
                "title": "Daily order trend",
                "answer_mode": "chart",
            },
        ],
        text_response="The daily order trend is shown in the attached chart.",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Show me the daily order trend")

    chart = result["artifacts"][0]
    assert chart["kind"] == "chart"
    assert len(chart["labels"]) > 12


def test_explicit_line_chart_type_is_preserved_for_non_time_labels():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Compare payment outcomes by status.",
                "complexity": "single_query",
                "target_tables": ["payments"],
                "stop_condition": "Once the payment status comparison is available.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": (
                    "SELECT status, COUNT(*) AS payment_count "
                    "FROM [payments] "
                    "GROUP BY status "
                    "ORDER BY payment_count DESC"
                ),
                "title": "Payment status comparison",
                "answer_mode": "chart",
                "chart_type": "line",
            },
        ],
        text_response="The payment status comparison is shown in the attached chart.",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Compare payment outcomes by status")

    chart = result["artifacts"][0]
    assert chart["kind"] == "chart"
    assert chart["chart_type"] == "line"


def test_explicit_funnel_chart_type_is_supported_for_stage_data():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Show the checkout funnel.",
                "complexity": "single_query",
                "target_tables": ["orders"],
                "stop_condition": "Once the funnel stages are available.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": (
                    "SELECT step_name, users FROM ("
                    "SELECT 'Orders created' AS step_name, COUNT(*) AS users, 1 AS step_order FROM [orders] "
                    "UNION ALL "
                    "SELECT 'Orders completed' AS step_name, COUNT(*) AS users, 2 AS step_order FROM [orders] WHERE order_status = 'completed'"
                    ") ORDER BY step_order"
                ),
                "title": "Checkout funnel",
                "answer_mode": "chart",
                "chart_type": "funnel",
            },
        ],
        text_response="The checkout funnel is shown in the attached chart.",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Show the checkout funnel")

    chart = result["artifacts"][0]
    assert chart["kind"] == "chart"
    assert chart["chart_type"] == "funnel"


def test_invalid_chart_type_falls_back_to_inferred_bar_chart():
    llm = StubLLM(
        json_responses=[
            {
                "question_understanding": "Compare payment outcomes by status.",
                "complexity": "single_query",
                "target_tables": ["payments"],
                "stop_condition": "Once payment status comparison is available.",
                "next_steps": [],
            },
            {
                "action": "sql",
                "sql": (
                    "SELECT status, COUNT(*) AS payment_count "
                    "FROM [payments] "
                    "GROUP BY status "
                    "ORDER BY payment_count DESC"
                ),
                "title": "Payment status comparison",
                "answer_mode": "chart",
                "chart_type": "scatter",
            },
        ],
        text_response="Payment status comparison is shown in the attached chart.",
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Compare payment outcomes by status")

    chart = result["artifacts"][0]
    assert chart["kind"] == "chart"
    assert chart["chart_type"] == "bar"


def test_scoped_sql_executor_rejects_unauthorized_tables():
    result = execute_authorized_select(
        scenario_id="checkout_conversion_drop",
        sql="SELECT * FROM [support_tickets]",
        allowed_tables={"orders", "payments", "users"},
        max_rows=5,
    )

    assert result["ok"] is False
    assert "unauthorized table access" in result["error"].lower()


def test_scoped_sql_executor_rejects_csv_style_table_names():
    result = execute_authorized_select(
        scenario_id="checkout_conversion_drop",
        sql="SELECT user_id, SUM(total_amount) AS total_spent FROM [orders.csv] GROUP BY user_id ORDER BY total_spent DESC",
        allowed_tables={"orders", "payments", "users"},
        max_rows=5,
    )

    assert result["ok"] is False
    assert "unauthorized table access" in result["error"].lower()


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
                "target_tables": ["orders"],
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
