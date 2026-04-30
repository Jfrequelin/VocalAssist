from __future__ import annotations

import unittest

from src.assistant.intents import INTENT_REGISTRY, parse_intent
from src.assistant.scenarios import compute_functional_coverage, load_scenarios


class TestScenarios(unittest.TestCase):
    def test_scenarios_are_not_empty(self) -> None:
        scenarios = load_scenarios()
        self.assertTrue(len(scenarios) > 0)

    def test_scenarios_have_required_keys(self) -> None:
        scenarios = load_scenarios()
        for scenario in scenarios:
            self.assertIn("user", scenario)
            self.assertIn("expected_intent", scenario)
            self.assertTrue(scenario["user"].strip())
            self.assertTrue(scenario["expected_intent"].strip())

    def test_scenarios_expected_intents_are_detected(self) -> None:
        scenarios = load_scenarios()
        for scenario in scenarios:
            detected = parse_intent(scenario["user"])
            self.assertEqual(detected, scenario["expected_intent"])

    def test_corpus_contains_unknown_negative_cases(self) -> None:
        scenarios = load_scenarios()
        negatives = [s for s in scenarios if s["expected_intent"] == "unknown"]
        self.assertGreaterEqual(len(negatives), 2)

    def test_functional_coverage_all_supported_intents(self) -> None:
        scenarios = load_scenarios()
        report = compute_functional_coverage(scenarios, set(INTENT_REGISTRY))

        self.assertEqual(report["missing_intents"], [])
        self.assertEqual(report["coverage_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
