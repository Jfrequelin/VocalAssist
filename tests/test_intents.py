from __future__ import annotations

import unittest

from src.assistant.intents import INTENT_REGISTRY, extract_slots, parse_intent, respond


class TestParseIntent(unittest.TestCase):
    def test_registry_contains_expected_intents(self) -> None:
        self.assertEqual(
            set(INTENT_REGISTRY),
            {
                "time",
                "date",
                "weather",
                "music",
                "light",
                "reminder",
                "agenda",
                "exit",
                "mute",
                "volume",
                "restart",
                "stop_media",
                "system_help",
                "temperature",
            },
        )

    def test_time(self) -> None:
        self.assertEqual(parse_intent("quelle heure est-il"), "time")

    def test_date(self) -> None:
        self.assertEqual(parse_intent("quelle est la date du jour"), "date")

    def test_weather(self) -> None:
        self.assertEqual(parse_intent("meteo"), "weather")

    def test_weather_with_accent(self) -> None:
        self.assertEqual(parse_intent("météo de Paris"), "weather")

    def test_light(self) -> None:
        self.assertEqual(parse_intent("allume la lumiere"), "light")

    def test_light_with_accent(self) -> None:
        self.assertEqual(parse_intent("allume la lumière"), "light")

    def test_music(self) -> None:
        self.assertEqual(parse_intent("lance une chanson"), "music")

    def test_reminder(self) -> None:
        self.assertEqual(parse_intent("cree un rappel"), "reminder")

    def test_agenda(self) -> None:
        self.assertEqual(parse_intent("agenda de demain"), "agenda")

    def test_exit(self) -> None:
        self.assertEqual(parse_intent("stop"), "exit")

    def test_unknown(self) -> None:
        self.assertEqual(parse_intent("blabla incomprehensible"), "unknown")

    def test_mute(self) -> None:
        self.assertEqual(parse_intent("active le mode mute"), "mute")

    def test_volume(self) -> None:
        self.assertEqual(parse_intent("augmente le volume"), "volume")

    def test_restart(self) -> None:
        self.assertEqual(parse_intent("redemarre le systeme"), "restart")

    def test_stop_media_priority_over_exit(self) -> None:
        self.assertEqual(parse_intent("stop la musique"), "stop_media")

    def test_system_help(self) -> None:
        self.assertEqual(parse_intent("aide systeme"), "system_help")

    def test_temperature(self) -> None:
        self.assertEqual(parse_intent("regle la temperature a 22"), "temperature")

    def test_extract_light_slots(self) -> None:
        slots = extract_slots("allume la lumiere du salon", "light")
        self.assertEqual(slots.get("state"), "on")
        self.assertEqual(slots.get("room"), "salon")

    def test_extract_music_slots(self) -> None:
        slots = extract_slots("lance de la musique rock volume 30", "music")
        self.assertEqual(slots.get("action"), "play")
        self.assertEqual(slots.get("genre"), "rock")
        self.assertEqual(slots.get("volume"), 30)

    def test_respond_music_volume_out_of_range(self) -> None:
        answer = respond("music", {"volume": 130})
        self.assertIn("entre 0 et 100", answer)

    def test_respond_temperature_requires_value(self) -> None:
        answer = respond("temperature", {})
        self.assertIn("Precisez la temperature", answer)

    def test_respond_temperature_with_value(self) -> None:
        answer = respond("temperature", {"value": 21})
        self.assertIn("21", answer)

    def test_known_intents_have_non_empty_response(self) -> None:
        for intent in INTENT_REGISTRY:
            self.assertTrue(respond(intent))


if __name__ == "__main__":
    unittest.main()
