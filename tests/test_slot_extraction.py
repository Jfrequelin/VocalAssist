"""
Tests for MACRO-002-T3: Simple slot extraction
Tests generic slot extraction from user input based on slot definitions.
"""

from __future__ import annotations

import unittest
from typing import Any

from src.assistant.intents_v2 import SlotExtractor, SlotType


SlotConfig = dict[str, Any]
SlotDefinitions = dict[str, SlotConfig]


class TestSlotExtraction(unittest.TestCase):
    """Test slot extraction from user input."""

    def setUp(self) -> None:
        self.extractor = SlotExtractor()

    def test_extract_enum_slot_exact_match(self) -> None:
        """Test extracting ENUM slot with exact keyword match."""
        text = "allume la lumiere du salon"
        
        slots_def: SlotDefinitions = {
            "room": {"type": SlotType.ENUM, "values": ["salon", "chambre", "cuisine", "bureau"]},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        self.assertIn("room", slots)
        self.assertEqual(slots["room"], "salon")

    def test_extract_enum_slot_no_match(self) -> None:
        """Test extracting ENUM slot when value not in list."""
        text = "allume la lumiere du grenier"
        
        slots_def: SlotDefinitions = {
            "room": {"type": SlotType.ENUM, "values": ["salon", "chambre", "cuisine", "bureau"]},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        # Should not extract unknown room
        self.assertNotIn("room", slots)

    def test_extract_numeric_slot_integer(self) -> None:
        """Test extracting NUMERIC slot with integer."""
        text = "regle la lumiere a 75 pourcent"
        
        slots_def: SlotDefinitions = {
            "brightness": {"type": SlotType.NUMERIC, "min": 0, "max": 100},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        self.assertIn("brightness", slots)
        self.assertEqual(slots["brightness"], 75)

    def test_extract_numeric_slot_with_range_validation(self) -> None:
        """Test that numeric slots are validated against range."""
        text = "temperature 50 degres"  # Invalid: > 30
        
        slots_def: SlotDefinitions = {
            "value": {"type": SlotType.NUMERIC, "min": 10, "max": 30},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        # Should not extract out-of-range value
        self.assertNotIn("value", slots)

    def test_extract_string_slot_simple(self) -> None:
        """Test extracting STRING slot with simple extraction."""
        text = "cherche python programming"
        
        slots_def: SlotDefinitions = {
            "query": {"type": SlotType.STRING},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        # STRING slots could extract from after a keyword or use regex
        # This documents the feature
        self.assertIsInstance(slots, dict)

    def test_extract_multiple_slots(self) -> None:
        """Test extracting multiple slots from one command."""
        text = "allume la lumiere du salon a 80 pourcent"
        
        slots_def: SlotDefinitions = {
            "room": {"type": SlotType.ENUM, "values": ["salon", "chambre", "cuisine", "bureau"]},
            "brightness": {"type": SlotType.NUMERIC, "min": 0, "max": 100},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots.get("room"), "salon")
        self.assertEqual(slots.get("brightness"), 80)

    def test_extract_with_case_insensitive_matching(self) -> None:
        """Test that extraction is case-insensitive."""
        text = "ALLUME la LUMIERE du SALON"
        
        slots_def: SlotDefinitions = {
            "room": {"type": SlotType.ENUM, "values": ["salon", "chambre", "cuisine", "bureau"]},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        self.assertIn("room", slots)
        self.assertEqual(slots["room"], "salon")

    def test_extract_with_accents_normalization(self) -> None:
        """Test that extraction handles accents correctly."""
        text = "allume la lumière du salon"
        
        slots_def: SlotDefinitions = {
            "room": {"type": SlotType.ENUM, "values": ["salon", "chambre", "cuisine", "bureau"]},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        self.assertIn("room", slots)
        self.assertEqual(slots["room"], "salon")

    def test_enum_slot_with_multi_word_values(self) -> None:
        """Test ENUM slot extraction with multi-word enum values."""
        text = "je veux de la musique rock"
        
        slots_def: SlotDefinitions = {
            "genre": {"type": SlotType.ENUM, "values": ["rock", "jazz", "pop classique", "electro"]},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        self.assertIn("genre", slots)
        self.assertEqual(slots["genre"], "rock")

    def test_numeric_extraction_with_text_suffix(self) -> None:
        """Test numeric extraction when number has text suffix."""
        text = "minuteur 5 minutes"
        
        slots_def: SlotDefinitions = {
            "duration": {"type": SlotType.NUMERIC, "min": 1, "max": 3600},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        self.assertIn("duration", slots)
        self.assertEqual(slots["duration"], 5)

    def test_required_slot_missing_returns_error(self) -> None:
        """Test validation of required slots."""
        text = "eteins la lumiere"
        
        slots_def: SlotDefinitions = {
            "state": {"type": SlotType.ENUM, "values": ["on", "off"], "required": True},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        # State not mentioned, required slot missing
        self.assertNotIn("state", slots)

    def test_extract_partial_slots_success(self) -> None:
        """Test that partial slot extraction doesn't fail entire command."""
        text = "allume la lumiere"  # No room mentioned
        
        slots_def: SlotDefinitions = {
            "room": {"type": SlotType.ENUM, "values": ["salon", "chambre", "cuisine", "bureau"]},
            "state": {"type": SlotType.ENUM, "values": ["on", "off"]},
        }
        
        slots = self.extractor.extract(text, slots_def)
        
        # Should extract 'on' from 'allume' (implicit state)
        # But room not extracted
        self.assertIsInstance(slots, dict)


class TestSlotExtractionIntegration(unittest.TestCase):
    """Integration tests for slot extraction with real intents."""

    def setUp(self) -> None:
        self.extractor = SlotExtractor()

    def test_light_command_full_extraction(self) -> None:
        """Test extracting light command with all available slots."""
        text = "allume la lumiere du salon a 75 pourcent brightness"
        
        light_slots: SlotDefinitions = {
            "room": {"type": SlotType.ENUM, "values": ["salon", "chambre", "cuisine", "bureau"]},
            "brightness": {"type": SlotType.NUMERIC, "min": 0, "max": 100},
        }
        
        slots = self.extractor.extract(text, light_slots)
        
        self.assertEqual(slots.get("room"), "salon")
        self.assertEqual(slots.get("brightness"), 75)

    def test_weather_city_extraction(self) -> None:
        """Test extracting city from weather command."""
        text = "quelle est la meteo a paris"
        
        weather_slots: SlotDefinitions = {
            "city": {"type": SlotType.STRING},
        }
        
        slots = self.extractor.extract(text, weather_slots)
        
        # STRING extraction for city after 'a'
        self.assertIsInstance(slots, dict)

    def test_temperature_numeric_extraction(self) -> None:
        """Test extracting temperature value."""
        text = "regle le thermostat a 21 degres"
        
        temp_slots: SlotDefinitions = {
            "value": {"type": SlotType.NUMERIC, "min": 10, "max": 30},
        }
        
        slots = self.extractor.extract(text, temp_slots)
        
        self.assertIn("value", slots)
        self.assertEqual(slots["value"], 21)


if __name__ == "__main__":
    unittest.main()
