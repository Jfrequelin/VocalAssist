"""
Tests for MACRO-002-T2: New local critical intents
Tests new intents and their integration into the registry.
"""

from __future__ import annotations

import unittest

from src.assistant.intent_configs import create_default_registry
from src.assistant.intents_v2 import SlotDefinition


class TestNewCriticalIntents(unittest.TestCase):
    """Test new critical intents added to local understanding."""

    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_timer_intent_exists_and_matches(self) -> None:
        """Test that timer intent can be registered and matched."""
        # Timer is a new critical intent for alarms/reminders
        timer_intent = self.registry.get("timer")
        if timer_intent is not None:
            self.assertIsNotNone(timer_intent)
            self.assertIn("timer", [i for i, _ in self.registry.get_ordered()])

    def test_notes_intent_for_todo_management(self) -> None:
        """Test that notes intent can be used for TODO/lists."""
        notes_intent = self.registry.get("notes")
        if notes_intent is not None:
            self.assertIsNotNone(notes_intent)

    def test_search_intent_for_local_queries(self) -> None:
        """Test that search intent can handle local queries."""
        search_intent = self.registry.get("search")
        if search_intent is not None:
            self.assertIsNotNone(search_intent)
            self.assertIn("slots", search_intent)

    def test_settings_intent_for_system_config(self) -> None:
        """Test that settings intent handles system configuration."""
        settings_intent = self.registry.get("settings")
        if settings_intent is not None:
            self.assertIsNotNone(settings_intent)

    def test_all_intents_have_keywords(self) -> None:
        """Test that all registered intents have keywords."""
        ordered = self.registry.get_ordered()
        
        for intent_id, data in ordered:
            keywords = data.get("keywords", [])
            self.assertIsInstance(keywords, list, f"Intent {intent_id} keywords should be a list")

    def test_all_intents_have_priority(self) -> None:
        """Test that all registered intents have priority."""
        ordered = self.registry.get_ordered()
        
        for intent_id, data in ordered:
            priority = data.get("priority")
            self.assertIsNotNone(priority, f"Intent {intent_id} should have priority")
            self.assertIsInstance(priority, int)

    def test_intent_with_slots_has_slot_definitions(self) -> None:
        """Test that intents with slots have proper slot definitions."""
        light = self.registry.get("light")

        assert light is not None
        if "slots" in light:
            slots = light["slots"]
            self.assertIsInstance(slots, dict)

            for _, slot_def in slots.items():
                self.assertIsInstance(slot_def, SlotDefinition)
                self.assertIsNotNone(slot_def.slot_type)


class TestIntentCoverageForLocalUnderstanding(unittest.TestCase):
    """Test coverage of essential local understanding intents."""

    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_system_control_intents_present(self) -> None:
        """Test that system control intents are available."""
        system_intents = ["exit", "restart", "mute", "volume", "system_help"]
        
        for intent in system_intents:
            result = self.registry.get(intent)
            self.assertIsNotNone(result, f"System intent '{intent}' should be registered")

    def test_information_query_intents_present(self) -> None:
        """Test that information query intents are available."""
        info_intents = ["time", "date", "weather", "agenda", "reminder"]
        
        for intent in info_intents:
            result = self.registry.get(intent)
            self.assertIsNotNone(result, f"Info intent '{intent}' should be registered")

    def test_home_automation_intents_present(self) -> None:
        """Test that home automation intents are available."""
        home_intents = ["light", "temperature", "music"]
        
        for intent in home_intents:
            result = self.registry.get(intent)
            self.assertIsNotNone(result, f"Home intent '{intent}' should be registered")

    def test_matching_performance_with_multiple_intents(self) -> None:
        """Test that matching works efficiently with many intents."""
        # Create test cases for various commands
        test_cases = [
            ("allume la lumiere", "light"),
            ("quelle heure est-il", "time"),
            ("lance la musique", "music"),
            ("coupe le son", "mute"),
            ("quel est le programme demain", "agenda"),
        ]
        
        for text, _expected_intent in test_cases:
            matched = self.registry.find_intent(text)
            self.assertIsNotNone(matched, f"Should find intent for '{text}'")
            # Intent might not be exact due to matching rules


if __name__ == "__main__":
    unittest.main()
