from __future__ import annotations

import unittest
from unittest.mock import patch

from src.assistant.orchestrator import handle_message


class TestOrchestrator(unittest.TestCase):
    def test_local_intent_keeps_local_source(self) -> None:
        reply = handle_message("quelle heure est-il", use_leon_fallback=True)
        self.assertEqual(reply.source, "local")
        self.assertEqual(reply.intent, "time")

    @patch("src.assistant.orchestrator.LeonClient")
    def test_critical_local_intent_does_not_call_leon(self, mock_leon_cls) -> None:
        reply = handle_message("stop la musique", use_leon_fallback=True)

        self.assertEqual(reply.source, "local")
        self.assertEqual(reply.intent, "stop_media")
        mock_leon_cls.from_env.assert_not_called()

    @patch("src.assistant.orchestrator.LeonClient")
    def test_temperature_local_slot_intent_does_not_call_leon(self, mock_leon_cls) -> None:
        reply = handle_message("regle la temperature a 22", use_leon_fallback=True)

        self.assertEqual(reply.source, "local")
        self.assertEqual(reply.intent, "temperature")
        self.assertIn("22", reply.answer)
        mock_leon_cls.from_env.assert_not_called()

    @patch("src.assistant.orchestrator.LeonClient")
    def test_unknown_uses_leon_when_available(self, mock_leon_cls) -> None:
        mock_leon = mock_leon_cls.from_env.return_value
        mock_leon.ask.return_value = "Reponse Leon"

        reply = handle_message("explique la theorie des cordes", use_leon_fallback=True)

        self.assertEqual(reply.intent, "unknown")
        self.assertEqual(reply.source, "leon")
        self.assertEqual(reply.answer, "Reponse Leon")

    @patch("src.assistant.orchestrator.LeonClient")
    def test_unknown_handles_unavailable_leon(self, mock_leon_cls) -> None:
        mock_leon = mock_leon_cls.from_env.return_value
        mock_leon.ask.return_value = None

        reply = handle_message("question inconnue", use_leon_fallback=True)

        self.assertEqual(reply.source, "fallback-error")
        self.assertIn("Leon", reply.answer)


if __name__ == "__main__":
    unittest.main()
