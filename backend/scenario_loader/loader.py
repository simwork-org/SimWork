from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from backend.config import get_settings
from backend.models import ScenarioSummary


@dataclass(slots=True)
class ScenarioBundle:
    scenario_id: str
    config: dict[str, Any]
    telemetry: dict[str, dict[str, Any]]


class ScenarioLoader:
    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path = base_path or get_settings().scenarios_path

    def list_scenarios(self) -> list[ScenarioSummary]:
        scenarios: list[ScenarioSummary] = []
        if not self.base_path.exists():
            return scenarios
        for scenario_dir in sorted(path for path in self.base_path.iterdir() if path.is_dir()):
            config_path = scenario_dir / "scenario_config.json"
            if not config_path.exists():
                continue
            config = json.loads(config_path.read_text())
            scenarios.append(
                ScenarioSummary(
                    id=config["scenario_id"],
                    title=config["title"],
                    difficulty=config["difficulty"],
                    industry=config.get("industry"),
                    product=config.get("product"),
                )
            )
        return scenarios

    def load_scenario(self, scenario_id: str) -> ScenarioBundle:
        scenario_dir = self.base_path / scenario_id
        if not scenario_dir.exists():
            raise FileNotFoundError(f"Scenario {scenario_id!r} not found")

        config = json.loads((scenario_dir / "scenario_config.json").read_text())
        telemetry: dict[str, dict[str, Any]] = {}

        for domain in ("analytics", "observability", "user_signals"):
            domain_dir = scenario_dir / domain
            if not domain_dir.exists():
                telemetry[domain] = {}
                continue
            domain_payload: dict[str, Any] = {}
            for file_path in sorted(domain_dir.iterdir()):
                key = file_path.stem
                if file_path.suffix == ".csv":
                    domain_payload[key] = pd.read_csv(file_path)
                elif file_path.suffix == ".json":
                    domain_payload[key] = json.loads(file_path.read_text())
                else:
                    domain_payload[key] = file_path.read_text()
            telemetry[domain] = domain_payload

        return ScenarioBundle(scenario_id=scenario_id, config=config, telemetry=telemetry)
