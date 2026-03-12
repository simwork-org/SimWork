"""Telemetry data layer — enforces domain access rules."""

from __future__ import annotations

from typing import Any

from scenario_loader.loader import load_telemetry

# Domain access rules per agent role
AGENT_DOMAIN_MAP: dict[str, str] = {
    "analyst": "analytics",
    "ux_researcher": "user_signals",
    "developer": "observability",
}

VALID_AGENTS = set(AGENT_DOMAIN_MAP.keys())


def get_domain_for_agent(agent: str) -> str:
    """Return the telemetry domain an agent is allowed to access."""
    if agent not in AGENT_DOMAIN_MAP:
        raise ValueError(f"Invalid agent: {agent}. Valid agents: {list(AGENT_DOMAIN_MAP.keys())}")
    return AGENT_DOMAIN_MAP[agent]


def get_telemetry_for_agent(scenario_id: str, agent: str) -> dict[str, Any]:
    """Load telemetry data scoped to the agent's allowed domain."""
    domain = get_domain_for_agent(agent)
    return load_telemetry(scenario_id, domain)


def format_telemetry_context(telemetry_data: dict[str, Any]) -> str:
    """Format telemetry data into a text context string for the LLM."""
    parts: list[str] = []
    for filename, content in telemetry_data.items():
        parts.append(f"--- {filename} ---")
        if isinstance(content, list):
            # CSV records
            for row in content:
                parts.append(str(row))
        elif isinstance(content, str):
            # Markdown content
            parts.append(content)
        elif isinstance(content, dict):
            import json

            parts.append(json.dumps(content, indent=2))
        else:
            parts.append(str(content))
        parts.append("")
    return "\n".join(parts)
