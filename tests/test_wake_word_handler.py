from __future__ import annotations

import unittest

from src.assistant.wake_word_handler import WakeWordHandler


class TestWakeWordHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = WakeWordHandler(wake_word="nova")

    def test_activation_with_valid_wake_word_and_command(self) -> None:
        result = self.handler.extract_command("nova allume la lumiere")
        self.assertTrue(result.activated)
        self.assertEqual(result.command, "allume la lumiere")

    def test_activation_case_insensitive(self) -> None:
        result = self.handler.extract_command("NOVA allume la lumiere")
        self.assertTrue(result.activated)
        self.assertEqual(result.command, "allume la lumiere")

    def test_no_activation_without_wake_word(self) -> None:
        result = self.handler.extract_command("allume la lumiere")
        self.assertFalse(result.activated)
        self.assertIsNone(result.command)

    def test_wake_word_only_returns_help(self) -> None:
        result = self.handler.extract_command("nova")
        self.assertTrue(result.activated)
        self.assertIsNone(result.command)
        self.assertTrue(result.is_help_requested)

    def test_multiple_words_extracted_after_wake_word(self) -> None:
        result = self.handler.extract_command("nova quelle est la temperature demain")
        self.assertTrue(result.activated)
        self.assertEqual(result.command, "quelle est la temperature demain")

    def test_extra_spaces_handled_correctly(self) -> None:
        result = self.handler.extract_command("nova   allume   la   lumiere")
        self.assertTrue(result.activated)
        self.assertEqual(result.command, "allume la lumiere")

    def test_custom_wake_word(self) -> None:
        handler = WakeWordHandler(wake_word="alexia")
        result = handler.extract_command("alexia quelle heure est-il")
        self.assertTrue(result.activated)
        self.assertEqual(result.command, "quelle heure est-il")

    def test_partial_wake_word_not_matched(self) -> None:
        result = self.handler.extract_command("nov allume la lumiere")
        self.assertFalse(result.activated)

    def test_wake_word_in_middle_not_activated(self) -> None:
        result = self.handler.extract_command("dis nova allume la lumiere")
        self.assertFalse(result.activated)

    def test_formatting_message(self) -> None:
        result = self.handler.extract_command("nova aide")
        self.assertTrue(result.activated)
        self.assertIsNone(result.command)
        self.assertTrue(result.is_help_requested)
        formatted = result.format_for_display()
        self.assertIn("aide", formatted.lower())


if __name__ == "__main__":
    unittest.main()
