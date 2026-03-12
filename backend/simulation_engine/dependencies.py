from __future__ import annotations

from functools import lru_cache

from backend.simulation_engine.service import SimulationEngine


@lru_cache(maxsize=1)
def get_engine() -> SimulationEngine:
    return SimulationEngine()
