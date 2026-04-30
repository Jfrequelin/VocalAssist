from __future__ import annotations

import unittest

from src.assistant.intents import parse_intent
from src.assistant.scenarios import load_scenarios


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


if __name__ == "__main__":
    unittest.main()
