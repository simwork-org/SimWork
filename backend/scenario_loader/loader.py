"""Scenario loader — reads scenario configs and reference data from the filesystem."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "scenarios"


def list_scenarios() -> list[dict[str, str]]:
    """Return metadata for every available scenario."""
    results: list[dict[str, str]] = []
    if not SCENARIOS_DIR.exists():
        return results
    for folder in sorted(SCENARIOS_DIR.iterdir()):
        config_path = folder / "scenario_config.json"
        if config_path.exists():
            cfg = json.loads(config_path.read_text())
            results.append(
                {
                    "id": cfg.get("scenario_id", folder.name),
                    "title": cfg.get("title", folder.name),
                    "difficulty": cfg.get("difficulty", "medium"),
                }
            )
    return results


def load_scenario(scenario_id: str) -> dict[str, Any]:
    """Load a full scenario config by ID."""
    scenario_dir = SCENARIOS_DIR / scenario_id
    config_path = scenario_dir / "scenario_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_id}")
    return json.loads(config_path.read_text())


def load_reference(scenario_id: str) -> dict[str, Any]:
    """Load candidate-facing scenario reference content if available."""
    reference_path = SCENARIOS_DIR / scenario_id / "reference.json"
    if not reference_path.exists():
        return {}
    return json.loads(reference_path.read_text())


def get_agent_data_access(scenario_id: str, agent: str) -> dict[str, Any]:
    """Return scenario-backed access metadata for an agent."""
    scenario = load_scenario(scenario_id)
    access = scenario.get("data_model", {}).get("agent_data_access", {}).get(agent)
    if not access:
        raise ValueError(f"Agent '{agent}' is not configured for scenario '{scenario_id}'")
    return access


def get_agent_capability_profile(scenario_id: str, agent: str) -> dict[str, Any]:
    """Return scenario-backed capability metadata for an agent."""
    scenario = load_scenario(scenario_id)
    profile = scenario.get("data_model", {}).get("agent_capability_profiles", {}).get(agent)
    if not profile:
        raise ValueError(f"Agent '{agent}' is missing a capability profile for scenario '{scenario_id}'")
    return profile


def get_agent_capability_profiles(scenario_id: str) -> dict[str, Any]:
    """Return all scenario-backed capability profiles."""
    scenario = load_scenario(scenario_id)
    return scenario.get("data_model", {}).get("agent_capability_profiles", {})


def load_tables(scenario_id: str, allowed_files: list[str]) -> dict[str, Any]:
    """Load specific table files from the scenario's SQLite database.

    Only loads files that appear in *allowed_files* (agent-scoped access control).
    Returns a dict mapping filename -> content.
    """
    from data_layer.db import get_document, query, table_exists

    data: dict[str, Any] = {}
    for filename in allowed_files:
        if filename.endswith(".csv"):
            tbl = filename.removesuffix(".csv")
            if table_exists(scenario_id, tbl):
                data[filename] = query(scenario_id, f"SELECT * FROM [{tbl}]")
        elif filename.endswith(".json"):
            # JSON files are still on filesystem
            file_path = SCENARIOS_DIR / scenario_id / "tables" / filename
            if file_path.exists():
                data[filename] = json.loads(file_path.read_text())
        elif filename.endswith(".md"):
            content = get_document(scenario_id, filename)
            if content is not None:
                data[filename] = content
    return data

