from __future__ import annotations

import unittest

from src.assistant.intents import parse_intent


class TestParseIntent(unittest.TestCase):
    def test_time(self) -> None:
        self.assertEqual(parse_intent("quelle heure est-il"), "time")

    def test_weather(self) -> None:
        self.assertEqual(parse_intent("meteo"), "weather")

    def test_light(self) -> None:
        self.assertEqual(parse_intent("allume la lumiere"), "light")

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


if __name__ == "__main__":
    unittest.main()
