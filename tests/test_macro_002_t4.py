"""
Tests for MACRO-002-T4: Comprehensive scenario coverage
Tests positive, negative, accents, and synonyms for intent recognition.
"""

from __future__ import annotations

import unittest

from src.assistant.intent_configs import create_default_registry


class TestIntentScenariosCoverage(unittest.TestCase):
    """Test comprehensive intent recognition scenarios."""

    def setUp(self) -> None:
        self.registry = create_default_registry()

    # ============ POSITIVE SCENARIOS ============

    def test_light_positive_scenarios(self) -> None:
        """Test positive scenarios for light intent."""
        positive_cases = [
            "allume la lumiere",
            "allume la lumiere du salon",
            "eteins la lampe",
            "eclairage du bureau",
            "lumiere de la cuisine",
        ]

        for text in positive_cases:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "light", f"Should recognize '{text}' as light intent")

    def test_music_positive_scenarios(self) -> None:
        """Test positive scenarios for music intent."""
        positive_cases = [
            "lance la musique",
            "joue une chanson",
            "radio",
            "musique rock",
            "play my playlist",
        ]

        for text in positive_cases:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "music", f"Should recognize '{text}' as music intent")

    def test_weather_positive_scenarios(self) -> None:
        """Test positive scenarios for weather intent."""
        positive_cases = [
            "quelle est la meteo",
            "meteo a paris",
            "temps aujourd'hui",
            "climat demain",
        ]

        for text in positive_cases:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "weather", f"Should recognize '{text}' as weather intent")

    def test_timer_positive_scenarios(self) -> None:
        """Test positive scenarios for timer intent."""
        positive_cases = [
            "minuteur 5 minutes",
            "set timer",
            "minuterie de cuisine",
            "10 minutes timer",
        ]

        for text in positive_cases:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "timer", f"Should recognize '{text}' as timer intent")

    # ============ NEGATIVE SCENARIOS ============

    def test_light_negative_scenarios(self) -> None:
        """Test that non-light commands don't match light intent."""
        negative_cases = [
            "quelle heure est-il",
            "lance la musique",
            "regle le thermostat",
        ]

        for text in negative_cases:
            matched = self.registry.find_intent(text)
            self.assertNotEqual(matched, "light", f"Should not recognize '{text}' as light intent")

    def test_music_negative_scenarios(self) -> None:
        """Test that non-music commands don't match music intent."""
        negative_cases = [
            "quelle temperature",
            "allume la lumiere",
            "donne moi la date",
        ]

        for text in negative_cases:
            matched = self.registry.find_intent(text)
            self.assertNotEqual(matched, "music", f"Should not recognize '{text}' as music intent")

    # ============ ACCENT SCENARIOS ============

    def test_weather_with_accents(self) -> None:
        """Test weather intent recognition with accents."""
        cases_with_accents = [
            "quelle est la météo",
            "temps à paris",
            "climat aujourd'hui",
            "météo à bordeaux",
        ]

        for text in cases_with_accents:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "weather", f"Should handle accents in '{text}'")

    def test_light_with_accents(self) -> None:
        """Test light intent with accents."""
        cases_with_accents = [
            "allume l'éclairage",
            "lumière de la chambre",
            "éteins la lampadaire",
        ]

        for text in cases_with_accents:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "light", f"Should handle accents in '{text}'")

    def test_calendar_with_accents(self) -> None:
        """Test agenda/calendar with accents."""
        cases_with_accents = [
            "qu'ai-je à l'agenda",
            "mon calendrier",
            "mon planning",
        ]

        for text in cases_with_accents:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "agenda", f"Should handle accents in '{text}'")

    # ============ SYNONYM SCENARIOS ============

    def test_exit_synonyms(self) -> None:
        """Test exit intent with various synonyms."""
        exit_synonyms = [
            "stop",
            "arrete",
            "quitte",
            "exit",
            "ferme",
            "bye",
            "aurevoir",
        ]

        for text in exit_synonyms:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "exit", f"Should recognize exit synonym: '{text}'")

    def test_music_synonyms(self) -> None:
        """Test music intent with synonyms."""
        music_synonyms = [
            "musique",
            "chanson",
            "radio",
            "play",
            "lance une chanson",
            "joue la musique",
        ]

        for text in music_synonyms:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "music", f"Should recognize music synonym: '{text}'")

    def test_timer_synonyms(self) -> None:
        """Test timer intent with synonyms."""
        timer_synonyms = [
            "minuteur",
            "timer",
            "minuterie",
            "set timer",
        ]

        for text in timer_synonyms:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "timer", f"Should recognize timer synonym: '{text}'")

    def test_notes_synonyms(self) -> None:
        """Test notes intent with synonyms."""
        notes_synonyms = [
            "notes",
            "todos",
            "ajoute une note",
            "liste mes notes",
            "ma liste de taches",
        ]

        for text in notes_synonyms:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "notes", f"Should recognize notes synonym: '{text}'")

    # ============ PRIORITY & AMBIGUITY RESOLUTION ============

    def test_exit_high_priority_over_others(self) -> None:
        """Test that exit has high priority and matches even with other keywords."""
        # 'stop' is in both exit and stop_media, but exit should win due to priority
        ambiguous_cases = [
            "stop tout",
            "stop immediatement",
        ]

        for text in ambiguous_cases:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, "exit", f"Exit should have priority for '{text}'")

    def test_ambiguous_unresolved_fallsback(self) -> None:
        """Test that unrecognized commands return None."""
        unrecognized_cases = [
            "raconte-moi une blague",
            "ouvre les rideaux",
            "xyz abc def",
            "fais moi un cafe",
        ]

        for text in unrecognized_cases:
            matched = self.registry.find_intent(text)
            self.assertIsNone(matched, f"Should not recognize '{text}'")

    # ============ MIXED CASE SCENARIOS ============

    def test_mixed_case_recognition(self) -> None:
        """Test intent recognition with various case combinations."""
        mixed_cases = [
            ("ALLUME LA LUMIERE", "light"),
            ("Quelle Heure Est-il", "time"),
            ("LaUnche La MuSique", "music"),
            ("STOP", "exit"),
        ]

        for text, expected_intent in mixed_cases:
            matched = self.registry.find_intent(text)
            self.assertEqual(matched, expected_intent, f"Should recognize mixed case '{text}'")


class TestIntentCoverageCompleteness(unittest.TestCase):
    """Test that coverage of scenarios is comprehensive."""

    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_simulation_scenarios_coverage(self) -> None:
        """Test that original simulation scenarios are still recognized."""
        from src.assistant.scenarios import load_scenarios

        scenarios = load_scenarios()
        coverage_count = 0

        for scenario in scenarios:
            text = scenario["user"]
            expected = scenario["expected_intent"]
            matched = self.registry.find_intent(text)

            if matched == expected:
                coverage_count += 1
            elif expected == "unknown" and matched is None:
                coverage_count += 1

        # Should cover most scenarios (some might be stricter)
        coverage_ratio = coverage_count / len(scenarios)
        self.assertGreater(coverage_ratio, 0.8, f"Should cover >80% of scenarios, got {coverage_ratio:.1%}")


if __name__ == "__main__":
    unittest.main()
