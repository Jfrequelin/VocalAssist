from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict


class Scenario(TypedDict):
    user: str
    expected_intent: str


def load_scenarios() -> list[Scenario]:
    root = Path(__file__).resolve().parents[2]
    scenario_file = root / "data" / "simulation_scenarios.json"

    with scenario_file.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return [
        {"user": str(item["user"]), "expected_intent": str(item["expected_intent"])}
        for item in raw
    ]
