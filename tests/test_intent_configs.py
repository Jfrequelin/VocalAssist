"""
Tests for intent slot extraction and validation.
MACRO-002-T1 extended: Slot extraction from configured intents.
"""

from __future__ import annotations

import unittest

from src.assistant.intent_configs import create_default_registry
from src.assistant.intents_v2 import SlotType


class TestDefaultIntentRegistry(unittest.TestCase):
    """Test predefined intent configurations."""

    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_registry_has_all_core_intents(self) -> None:
        """Test that default registry has essential intents."""
        core_intents = ["time", "date", "light", "music", "weather", "temperature", "exit"]

        for intent_id in core_intents:
            intent = self.registry.get(intent_id)
            self.assertIsNotNone(intent, f"Intent '{intent_id}' should be registered")

    def test_light_intent_has_required_slots(self) -> None:
        """Test that light intent has room and state slots."""
        light = self.registry.get("light")
        assert light is not None
        self.assertIn("slots", light)
        self.assertIn("room", light["slots"])
        self.assertIn("state", light["slots"])

        # Verify slot types
        self.assertEqual(light["slots"]["room"].slot_type, SlotType.ENUM)
        self.assertEqual(light["slots"]["state"].slot_type, SlotType.ENUM)

    def test_weather_has_city_slot(self) -> None:
        """Test that weather intent has city slot."""
        weather = self.registry.get("weather")
        assert weather is not None
        self.assertIn("city", weather["slots"])
        self.assertEqual(weather["slots"]["city"].slot_type, SlotType.STRING)

    def test_temperature_has_numeric_slot(self) -> None:
        """Test that temperature intent has numeric value slot."""
        temp = self.registry.get("temperature")
        assert temp is not None
        self.assertIn("value", temp["slots"])
        self.assertEqual(temp["slots"]["value"].slot_type, SlotType.NUMERIC)
        self.assertEqual(temp["slots"]["value"].min_value, 10)
        self.assertEqual(temp["slots"]["value"].max_value, 30)

    def test_music_intent_has_multiple_slots(self) -> None:
        """Test that music intent has action, genre, and volume slots."""
        music = self.registry.get("music")
        assert music is not None

        for slot_name in ["action", "genre", "volume"]:
            self.assertIn(slot_name, music["slots"])

    def test_priority_ordering_is_correct(self) -> None:
        """Test that intents are ordered by priority."""
        ordered = self.registry.get_ordered()
        priorities = [data["priority"] for _, data in ordered]

        # Should be in descending order
        for i in range(len(priorities) - 1):
            self.assertGreaterEqual(priorities[i], priorities[i + 1])

    def test_exit_intent_has_highest_priority(self) -> None:
        """Test that exit intent has highest priority."""
        ordered = self.registry.get_ordered()
        first_intent_id = ordered[0][0]
        self.assertEqual(first_intent_id, "exit")

    def test_find_light_intent(self) -> None:
        """Test finding light intent from text."""
        matched = self.registry.find_intent("allume la lumiere du salon")
        self.assertEqual(matched, "light")

    def test_find_weather_intent(self) -> None:
        """Test finding weather intent from text."""
        matched = self.registry.find_intent("quelle est la meteo a paris")
        self.assertEqual(matched, "weather")

    def test_find_music_intent(self) -> None:
        """Test finding music intent from text."""
        matched = self.registry.find_intent("lance une chanson rock")
        self.assertEqual(matched, "music")

    def test_find_time_intent(self) -> None:
        """Test finding time intent from text."""
        matched = self.registry.find_intent("quelle heure est-il")
        self.assertEqual(matched, "time")

    def test_find_exit_intent_high_priority(self) -> None:
        """Test that exit intent is matched even with other keywords."""
        # "stop" is in exit keywords, should match exit not music
        matched = self.registry.find_intent("stop la musique")
        self.assertEqual(matched, "exit")


class TestSlotExtraction(unittest.TestCase):
    """Test extracting slots from user input (to be implemented)."""

    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_extract_room_from_light_command(self) -> None:
        """Test extracting room slot from light command."""
        # This test documents the slot extraction feature
        # Implementation would use regex patterns defined in slot_definition
        light_intent = self.registry.get("light")
        assert light_intent is not None
        room_slot = light_intent["slots"]["room"]

        # Room slot should enumerate valid rooms
        self.assertIn("salon", room_slot.enum_values)
        self.assertIn("chambre", room_slot.enum_values)
        self.assertIn("cuisine", room_slot.enum_values)
        self.assertIn("bureau", room_slot.enum_values)

    def test_temperature_range_validation(self) -> None:
        """Test that temperature values have valid range."""
        temp_intent = self.registry.get("temperature")
        assert temp_intent is not None
        value_slot = temp_intent["slots"]["value"]

        self.assertEqual(value_slot.min_value, 10)
        self.assertEqual(value_slot.max_value, 30)


if __name__ == "__main__":
    unittest.main()
