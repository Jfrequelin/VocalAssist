from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict


class Scenario(TypedDict):
    user: str
    expected_intent: str


class CoverageReport(TypedDict):
    covered_intents: list[str]
    missing_intents: list[str]
    coverage_ratio: float


def load_scenarios() -> list[Scenario]:
    root = Path(__file__).resolve().parents[2]
    scenario_file = root / "data" / "simulation_scenarios.json"

    with scenario_file.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return [
        {"user": str(item["user"]), "expected_intent": str(item["expected_intent"])}
        for item in raw
    ]


def compute_functional_coverage(
    scenarios: list[Scenario],
    supported_intents: set[str],
) -> CoverageReport:
    covered = {scenario["expected_intent"] for scenario in scenarios if scenario["expected_intent"] != "unknown"}
    missing = sorted(supported_intents - covered)
    ratio = (len(covered) / len(supported_intents)) if supported_intents else 1.0

    return {
        "covered_intents": sorted(covered),
        "missing_intents": missing,
        "coverage_ratio": ratio,
    }
