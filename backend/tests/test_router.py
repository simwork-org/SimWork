from __future__ import annotations

from agent_router.evidence import execute_operations
from agent_router.router import route_query


class StubLLM:
    def __init__(self, planner=None, planner_error: Exception | None = None, synthesis_text: str | None = None):
        self.planner = planner
        self.planner_error = planner_error
        self.synthesis_text = synthesis_text

    def chat(self, system: str, user: str):
        if self.planner_error:
            raise self.planner_error
        return self.planner

    def chat_text(self, system: str, user: str) -> str:
        if self.synthesis_text is None:
            raise RuntimeError("force deterministic synthesis")
        return self.synthesis_text


def test_ambiguous_first_customer_returns_tie_warning():
    llm = StubLLM(
        planner={
            "intent": "lookup",
            "answer_mode": "table",
            "operations": [
                {
                    "type": "lookup_rows",
                    "source": "users.csv",
                    "title": "Earliest signed up users",
                    "columns": ["user_id", "name", "signup_date"],
                    "sort_by": "signup_date",
                    "sort_order": "asc",
                    "limit": 1,
                }
            ],
            "needs_clarification": None,
            "next_steps": [],
        }
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Who is our first customer?")

    assert result["artifacts"]
    assert result["artifacts"][0]["kind"] == "table"
    assert len(result["artifacts"][0]["rows"]) == 8
    assert result["citations"]
    assert any("ambiguous" in warning.lower() for warning in result["warnings"])
    assert "ambiguous" in result["response"].lower()


def test_planner_parse_failure_uses_safe_fallback_with_citations():
    llm = StubLLM(planner_error=ValueError("bad planner json"))

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Show daily order trends overall")

    assert result["artifacts"]
    assert result["artifacts"][0]["kind"] == "chart"
    assert result["artifacts"][0]["chart_type"] == "line"
    assert result["citations"]
    assert all(artifact["citation_ids"] for artifact in result["artifacts"])
    assert any("fallback" in warning.lower() for warning in result["warnings"])


def test_wrong_agent_query_redirects_instead_of_guessing():
    llm = StubLLM(planner={})

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Show the latest support ticket complaints")

    assert result["artifacts"] == []
    assert result["citations"] == []
    assert "ux researcher" in result["response"].lower()


def test_user_specific_lookup_flow_returns_evidence_table():
    llm = StubLLM(
        planner={
            "intent": "lookup",
            "answer_mode": "table",
            "operations": [
                {
                    "type": "lookup_rows",
                    "source": "orders.csv",
                    "title": "U02890 order history",
                    "filters": {"user_id": "U02890"},
                    "columns": ["order_id", "created_at", "order_status", "total_amount"],
                    "sort_by": "created_at",
                    "sort_order": "asc",
                    "limit": 20,
                }
            ],
            "needs_clarification": None,
            "next_steps": [],
        }
    )

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Show me U02890's order history")

    assert result["artifacts"][0]["kind"] == "table"
    assert 1 <= len(result["artifacts"][0]["rows"]) <= 20
    assert result["citations"][0]["source"] == "orders.csv"


def test_affirmative_follow_up_uses_pending_follow_up_default_choice():
    llm = StubLLM(planner_error=ValueError("bad planner json"))
    history = [
        {
            "agent": "analyst",
            "query": "plot the orders trend over time",
            "response": "Here is the orders trend over time.",
            "artifacts": [
                {
                    "kind": "chart",
                    "title": "Orders trend over time",
                    "chart_type": "line",
                    "labels": ["2024-12-15", "2024-12-16"],
                    "series": [{"name": "count", "values": [100, 90]}],
                    "citation_ids": ["ev_prev"],
                }
            ],
            "citations": [
                {
                    "citation_id": "ev_prev",
                    "source": "orders.csv",
                    "title": "Orders trend over time",
                    "summary": "Computed daily order counts from orders.csv.",
                }
            ],
            "warnings": [],
            "planner": {
                "next_steps": ["Break down the previous trend by platform."],
                "pending_follow_up": {
                    "prompt": "Would you like to break down the trend further?",
                    "choices": [
                        "Break down the previous trend by platform.",
                        "Break down the previous trend by order status.",
                        "Show the previous trend aggregated monthly.",
                    ],
                    "default_choice": "Break down the previous trend by platform.",
                    "resolved_query_template": "{choice}",
                },
                "effective_query": "plot the orders trend over time",
            },
        }
    ]

    result = route_query(llm, "checkout_conversion_drop", "analyst", "yes", conversation_history=history)

    assert result["artifacts"]
    assert result["artifacts"][0]["kind"] == "chart"
    assert result["artifacts"][0]["chart_type"] == "line"
    assert len(result["artifacts"][0]["series"]) >= 1
    assert result["_planner"]["effective_query"] == "Break down the previous trend by platform."
    assert any("short affirmative" in warning.lower() for warning in result["warnings"])


def test_partial_follow_up_reply_maps_to_matching_pending_choice():
    llm = StubLLM(planner_error=ValueError("bad planner json"))
    history = [
        {
            "agent": "analyst",
            "query": "plot the orders trend over time",
            "response": "Here is the orders trend over time.",
            "artifacts": [],
            "citations": [],
            "warnings": [],
            "planner": {
                "pending_follow_up": {
                    "prompt": "Would you like to break down the trend further?",
                    "choices": [
                        "Break down the previous trend by platform.",
                        "Break down the previous trend by order status.",
                        "Show the previous trend aggregated monthly.",
                    ],
                    "default_choice": "Break down the previous trend by platform.",
                    "resolved_query_template": "{choice}",
                },
                "effective_query": "plot the orders trend over time",
            },
        }
    ]

    result = route_query(llm, "checkout_conversion_drop", "analyst", "monthly", conversation_history=history)

    assert result["artifacts"]
    assert result["_planner"]["effective_query"] == "Show the previous trend aggregated monthly."
    assert result["artifacts"][0]["title"] == "Monthly Orders Trend"
    assert all(len(label) == 7 for label in result["artifacts"][0]["labels"])


def test_unmatched_short_follow_up_reply_returns_clarification():
    llm = StubLLM(planner_error=ValueError("bad planner json"))
    history = [
        {
            "agent": "analyst",
            "query": "plot the orders trend over time",
            "response": "Here is the orders trend over time.",
            "artifacts": [],
            "citations": [],
            "warnings": [],
            "planner": {
                "pending_follow_up": {
                    "prompt": "Would you like to break down the trend further?",
                    "choices": [
                        "Break down the previous trend by platform.",
                        "Break down the previous trend by order status.",
                    ],
                    "default_choice": "Break down the previous trend by platform.",
                    "resolved_query_template": "{choice}",
                },
                "effective_query": "plot the orders trend over time",
            },
        }
    ]

    result = route_query(llm, "checkout_conversion_drop", "analyst", "maybe", conversation_history=history)

    assert result["artifacts"] == []
    assert "choose one of these" in result["response"].lower()
    assert result["pending_follow_up"]["choices"] == [
        "Break down the previous trend by platform.",
        "Break down the previous trend by order status.",
    ]


def test_monthly_timeseries_artifact_uses_month_level_labels():
    result = execute_operations(
        scenario_id="checkout_conversion_drop",
        agent="analyst",
        operations=[
            {
                "type": "aggregate_timeseries",
                "source": "orders.csv",
                "metric": "order_id",
                "agg": "count",
                "granularity": "month",
                "title": "Trend analysis",
            }
        ],
        query_text="show monthly orders trend",
        answer_mode="chart",
        intent_class="trend_analysis",
    )

    assert result["artifacts"]
    assert result["artifacts"][0]["title"] == "Monthly Orders Trend"
    assert all(len(label) == 7 for label in result["artifacts"][0]["labels"])


def test_timeseries_title_is_renamed_when_requested_granularity_conflicts():
    result = execute_operations(
        scenario_id="checkout_conversion_drop",
        agent="analyst",
        operations=[
            {
                "type": "aggregate_timeseries",
                "source": "orders.csv",
                "metric": "order_id",
                "agg": "count",
                "granularity": "day",
                "title": "Monthly Orders Trend",
            }
        ],
        query_text="show orders trend",
        answer_mode="chart",
        intent_class="trend_analysis",
    )

    assert result["artifacts"]
    assert result["artifacts"][0]["title"] == "Daily Orders Trend"
    assert any("renamed artifact" in warning.lower() for warning in result["warnings"])


def test_dataset_summary_query_stays_inline_only():
    llm = StubLLM(planner_error=ValueError("bad planner json"))

    result = route_query(llm, "checkout_conversion_drop", "analyst", "Give me a quick summary of each dataset")

    assert result["intent_class"] == "dataset_summary"
    assert result["artifacts"]
    assert all(artifact["display_mode"] == "inline_only" for artifact in result["artifacts"])
    assert all(artifact["purpose"] == "reference" for artifact in result["artifacts"])
    assert "orders.csv" in result["response"].lower()


def test_engineering_incident_timeline_artifact_is_board_eligible():
    result = execute_operations(
        scenario_id="checkout_conversion_drop",
        agent="engineering_lead",
        operations=[
            {
                "type": "build_incident_timeline",
                "source": "deployments.csv",
                "title": "Recent deployment timeline",
                "limit": 5,
            }
        ],
        query_text="Show the recent deployment timeline",
        answer_mode="table",
        intent_class="incident_timeline",
    )

    assert result["artifacts"]
    artifact = result["artifacts"][0]
    assert artifact["display_mode"] == "board_default"
    assert artifact["purpose"] == "final_evidence"
    assert artifact["card_variant"] == "timeline"
