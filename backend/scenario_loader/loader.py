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
                    "description": cfg.get("problem_statement", ""),
                    "scenario_type": cfg.get("scenario_type", "diagnostic"),
                    "industry": cfg.get("industry"),
                    "product": cfg.get("product"),
                    "icon": cfg.get("icon"),
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


def get_agent_role_config(scenario_id: str, agent: str) -> dict[str, Any]:
    """Return merged role config with persona, skills, and allowed sources."""
    profile = get_agent_capability_profile(scenario_id, agent)
    access = get_agent_data_access(scenario_id, agent)
    raw_tables = access.get("tables", [])
    raw_documents = access.get("documents", [])
    allowed_tables = [name for name in raw_tables if not str(name).endswith(".md")]
    allowed_documents = [name for name in raw_documents if str(name).endswith(".md")]
    if not raw_documents:
        allowed_documents = [name for name in raw_tables if str(name).endswith(".md")]
    return {
        **profile,
        "allowed_tables": allowed_tables,
        "allowed_documents": allowed_documents,
        "access_description": access.get("description", ""),
    }


def get_agent_capability_profiles(scenario_id: str) -> dict[str, Any]:
    """Return all scenario-backed capability profiles."""
    scenario = load_scenario(scenario_id)
    return scenario.get("data_model", {}).get("agent_capability_profiles", {})


def load_tables(scenario_id: str, allowed_sources: list[str]) -> dict[str, Any]:
    """Load specific sources from the scenario's SQLite database.

    Only loads sources that appear in *allowed_sources* (agent-scoped access control).
    Returns a dict mapping source name -> content.
    """
    from data_layer.db import get_document, query, table_exists

    data: dict[str, Any] = {}
    for source_name in allowed_sources:
        if source_name.endswith(".md"):
            content = get_document(scenario_id, source_name)
            if content is not None:
                data[source_name] = content
        elif source_name.endswith(".json"):
            # JSON files are still on filesystem
            file_path = SCENARIOS_DIR / scenario_id / "tables" / source_name
            if file_path.exists():
                data[source_name] = json.loads(file_path.read_text())
        elif table_exists(scenario_id, source_name):
            data[source_name] = query(scenario_id, f"SELECT * FROM [{source_name}]")
    return data
