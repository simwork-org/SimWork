"""Scenario loader — reads scenario configs and telemetry data from the filesystem."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

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


def load_telemetry(scenario_id: str, domain: str) -> dict[str, Any]:
    """Load all telemetry files for a given domain.

    Returns a dict mapping filename -> content (DataFrame as records for CSV,
    raw text for markdown, parsed JSON for .json).
    """
    domain_dir = SCENARIOS_DIR / scenario_id / domain
    if not domain_dir.exists():
        raise FileNotFoundError(f"Domain data not found: {scenario_id}/{domain}")

    data: dict[str, Any] = {}
    for file_path in sorted(domain_dir.iterdir()):
        if file_path.suffix == ".csv":
            df = pd.read_csv(file_path)
            data[file_path.name] = df.to_dict(orient="records")
        elif file_path.suffix == ".json":
            data[file_path.name] = json.loads(file_path.read_text())
        elif file_path.suffix == ".md":
            data[file_path.name] = file_path.read_text()
        # skip unknown extensions
    return data
