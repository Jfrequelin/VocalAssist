"""
Tests for MACRO-002-T1: Centralized intent structure
Tests a unified intent definition system with slot extraction and validation.
"""

from __future__ import annotations

import unittest

from src.assistant.intents_v2 import IntentRegistry, SlotDefinition, SlotType


class TestIntentRegistryV2(unittest.TestCase):
    """Test new centralized intent registry structure."""

    def setUp(self) -> None:
        self.registry = IntentRegistry()

    def test_register_simple_intent_with_keywords(self) -> None:
        """Test registering a simple intent without slots."""
        self.registry.register(
            intent_id="greet",
            keywords=["bonjour", "salut", "hello"],
            priority=50,
            response_template="Bonjour! Comment puis-je vous aider?",
        )

        result = self.registry.get("greet")
        assert result is not None
        self.assertEqual(result["keywords"], ["bonjour", "salut", "hello"])
        self.assertEqual(result["priority"], 50)

    def test_register_intent_with_slots(self) -> None:
        """Test registering an intent with slot definitions."""
        light_slots = {
            "room": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["salon", "chambre", "cuisine", "bureau"],
                required=False,
            ),
            "state": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["on", "off"],
                required=True,
            ),
        }

        self.registry.register(
            intent_id="light",
            keywords=["lumiere", "eclairage", "lumiere du"],
            priority=80,
            slots=light_slots,
            response_template="Lumière {room}: {state}",
        )

        result = self.registry.get("light")
        assert result is not None
        self.assertIn("slots", result)
        self.assertIn("room", result["slots"])
        self.assertIn("state", result["slots"])

    def test_slot_definition_with_validation_rules(self) -> None:
        """Test slot definition with custom validation."""
        temp_slot = SlotDefinition(
            slot_type=SlotType.NUMERIC,
            required=True,
            min_value=10,
            max_value=30,
        )

        self.assertEqual(temp_slot.min_value, 10)
        self.assertEqual(temp_slot.max_value, 30)

    def test_priority_ordering(self) -> None:
        """Test that intents are ordered by priority."""
        self.registry.register("exit", keywords=["stop", "exit"], priority=100)
        self.registry.register("unknown", keywords=["xyz"], priority=1)
        self.registry.register("help", keywords=["aide"], priority=50)

        ordered = self.registry.get_ordered()
        priorities = [data["priority"] for _, data in ordered]

        # Should be in descending priority order
        self.assertEqual(priorities, [100, 50, 1])

    def test_keyword_matching_with_normalization(self) -> None:
        """Test that keyword matching works with text normalization."""
        self.registry.register("greet", keywords=["bonjour"])

        # Exact match
        self.assertTrue(self.registry.matches_keywords("bonjour", ["bonjour"]))

        # Case insensitive
        self.assertTrue(self.registry.matches_keywords("BONJOUR", ["bonjour"]))

        # With accents
        self.assertTrue(self.registry.matches_keywords("bonjour", ["bonjour"]))

    def test_keyword_word_boundary_matching(self) -> None:
        """Test that single-word keywords use word boundaries."""
        self.registry.register("light", keywords=["lumiere"])

        # Should match with word boundary
        self.assertTrue(self.registry.matches_keywords("allume la lumiere", ["lumiere"]))

        # Should NOT match as substring (word boundary)
        self.assertFalse(self.registry.matches_keywords("lumieresque", ["lumiere"]))

    def test_multi_word_keyword_exact_match(self) -> None:
        """Test that multi-word keywords require exact substring match."""
        self.registry.register("help", keywords=["aide systeme"])

        self.assertTrue(self.registry.matches_keywords("aide systeme disponible", ["aide systeme"]))
        self.assertFalse(self.registry.matches_keywords("aide system", ["aide systeme"]))

    def test_slot_extraction_from_registry(self) -> None:
        """Test that slot definitions are retrievable from registry."""
        slots_def = {
            "city": SlotDefinition(
                slot_type=SlotType.STRING,
                required=False,
            ),
        }

        self.registry.register(
            "weather",
            keywords=["meteo"],
            slots=slots_def,
        )

        result = self.registry.get("weather")
        assert result is not None
        self.assertIn("city", result["slots"])
        self.assertEqual(result["slots"]["city"].slot_type, SlotType.STRING)

    def test_intent_not_found_returns_none(self) -> None:
        """Test that getting non-existent intent returns None."""
        result = self.registry.get("nonexistent")
        self.assertIsNone(result)

    def test_find_matching_intent_by_keywords(self) -> None:
        """Test finding an intent by matching keywords against text."""
        self.registry.register("light", keywords=["lumiere", "eclairage"], priority=80)
        self.registry.register("exit", keywords=["stop", "exit"], priority=100)

        # Should match "light" (lumiere keyword)
        matched = self.registry.find_intent("allume la lumiere")
        self.assertEqual(matched, "light")

        # Should match "exit" (higher priority, stop keyword)
        matched = self.registry.find_intent("stop tout")
        self.assertEqual(matched, "exit")

        # Should return None if no match
        self.registry.register("unknown", keywords=[], priority=1)
        matched = self.registry.find_intent("xyz abc def")
        self.assertIsNone(matched)


class TestSlotDefinition(unittest.TestCase):
    """Test SlotDefinition configuration structure."""

    def test_enum_slot_definition(self) -> None:
        """Test defining an ENUM slot."""
        slot = SlotDefinition(
            slot_type=SlotType.ENUM,
            enum_values=["on", "off", "toggle"],
            required=True,
        )

        self.assertEqual(slot.slot_type, SlotType.ENUM)
        self.assertEqual(slot.enum_values, ["on", "off", "toggle"])
        self.assertTrue(slot.required)

    def test_numeric_slot_definition(self) -> None:
        """Test defining a NUMERIC slot with range."""
        slot = SlotDefinition(
            slot_type=SlotType.NUMERIC,
            min_value=0,
            max_value=100,
            required=False,
        )

        self.assertEqual(slot.slot_type, SlotType.NUMERIC)
        self.assertEqual(slot.min_value, 0)
        self.assertEqual(slot.max_value, 100)
        self.assertFalse(slot.required)

    def test_string_slot_definition(self) -> None:
        """Test defining a STRING slot."""
        slot = SlotDefinition(
            slot_type=SlotType.STRING,
            required=False,
        )

        self.assertEqual(slot.slot_type, SlotType.STRING)
        self.assertFalse(slot.required)


if __name__ == "__main__":
    unittest.main()
