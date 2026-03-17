"""Telemetry data layer — enforces domain access rules.

Each agent role has access to a specific set of tables under
scenarios/<scenario_id>/tables/. This module defines those access rules.
"""

from __future__ import annotations


# Which database tables/documents each agent role can access
AGENT_TABLE_ACCESS: dict[str, list[str]] = {
    "analyst": [
        "users",
        "orders",
        "order_items",
        "payments",
        "restaurants",
        "menu_items",
        "drivers",
        "funnel_events",
    ],
    "ux_researcher": [
        "reviews",
        "support_tickets",
        "usability_study.md",
        "ux_changelog",
    ],
    "engineering_lead": [
        "deployments",
        "service_metrics",
        "system_architecture.md",
        "error_log",
    ],
}

VALID_AGENTS = set(AGENT_TABLE_ACCESS.keys())
