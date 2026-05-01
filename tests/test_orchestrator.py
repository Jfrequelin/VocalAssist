from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from src.assistant.orchestrator import (
    LEON_CIRCUIT_BREAKER,
    handle_message,
    reset_leon_circuit_breaker,
    reset_pending_clarifications,
)


class TestOrchestrator(unittest.TestCase):
    def setUp(self) -> None:
        reset_leon_circuit_breaker()
        reset_pending_clarifications()
        LEON_CIRCUIT_BREAKER.failure_threshold = 3
        LEON_CIRCUIT_BREAKER.cooldown_seconds = 30.0

    def test_local_intent_keeps_local_source(self) -> None:
        reply = handle_message("quelle heure est-il", use_leon_fallback=True)
        self.assertEqual(reply.source, "local")
        self.assertEqual(reply.intent, "time")
        self.assertEqual(reply.routing_trace.get("route"), "local")
        self.assertTrue(reply.correlation_id)
        self.assertEqual(reply.routing_trace.get("correlation_id"), reply.correlation_id)

    def test_explicit_correlation_id_is_propagated(self) -> None:
        reply = handle_message("quelle heure est-il", use_leon_fallback=True, correlation_id="cid-123")
        self.assertEqual(reply.correlation_id, "cid-123")
        self.assertEqual(reply.routing_trace.get("correlation_id"), "cid-123")

    @patch("src.assistant.orchestrator.LeonClient")
    def test_critical_local_intent_does_not_call_leon(self, mock_leon_cls: Any) -> None:
        reply = handle_message("stop la musique", use_leon_fallback=True)

        self.assertEqual(reply.source, "local")
        self.assertEqual(reply.intent, "stop_media")
        self.assertEqual(reply.routing_trace.get("route"), "local")
        mock_leon_cls.from_env.assert_not_called()

    @patch("src.assistant.orchestrator.LeonClient")
    def test_temperature_local_slot_intent_does_not_call_leon(self, mock_leon_cls: Any) -> None:
        reply = handle_message("regle la temperature a 22", use_leon_fallback=True)

        self.assertEqual(reply.source, "local")
        self.assertEqual(reply.intent, "temperature")
        self.assertIn("22", reply.answer)
        self.assertEqual(reply.routing_trace.get("route"), "local")
        mock_leon_cls.from_env.assert_not_called()

    @patch("src.assistant.orchestrator.LeonClient")
    def test_unknown_uses_leon_when_available(self, mock_leon_cls: Any) -> None:
        mock_leon: Any = mock_leon_cls.from_env.return_value
        mock_leon.ask.return_value = "Reponse Leon"

        reply = handle_message("explique la theorie des cordes", use_leon_fallback=True)

        self.assertEqual(reply.intent, "unknown")
        self.assertEqual(reply.source, "leon")
        self.assertEqual(reply.answer, "Reponse Leon")
        self.assertEqual(reply.routing_trace.get("route"), "leon")

    @patch("src.assistant.orchestrator.LeonClient")
    def test_unknown_handles_unavailable_leon(self, mock_leon_cls: Any) -> None:
        mock_leon: Any = mock_leon_cls.from_env.return_value
        mock_leon.ask.return_value = None

        reply = handle_message("question inconnue", use_leon_fallback=True)

        self.assertEqual(reply.source, "fallback-error")
        self.assertIn("Leon", reply.answer)
        self.assertEqual(reply.routing_trace.get("route"), "fallback-error")

    def test_unknown_without_fallback_is_traceable(self) -> None:
        reply = handle_message("question inconnue", use_leon_fallback=False)

        self.assertEqual(reply.source, "local")
        self.assertEqual(reply.routing_trace.get("reason"), "fallback_disabled")

    def test_light_missing_room_triggers_clarification(self) -> None:
        reply = handle_message("allume la lumiere", use_leon_fallback=True, conversation_id="conv-1")

        self.assertEqual(reply.intent, "light")
        self.assertEqual(reply.source, "local-clarification")
        self.assertEqual(reply.routing_trace.get("route"), "local-clarification")
        self.assertEqual(reply.routing_trace.get("slot"), "room")
        self.assertIn("piece", reply.answer.lower())

    def test_clarification_followup_resolves_light_room(self) -> None:
        first = handle_message("allume la lumiere", use_leon_fallback=True, conversation_id="conv-2")
        self.assertEqual(first.source, "local-clarification")

        second = handle_message("salon", use_leon_fallback=True, conversation_id="conv-2")
        self.assertEqual(second.source, "local")
        self.assertEqual(second.intent, "light")
        self.assertEqual(second.routing_trace.get("reason"), "clarification_resolved")
        self.assertIn("salon", second.answer)

    def test_light_ambiguous_room_triggers_clarification(self) -> None:
        reply = handle_message(
            "allume la lumiere du salon ou de la cuisine",
            use_leon_fallback=True,
            conversation_id="conv-3",
        )
        self.assertEqual(reply.source, "local-clarification")
        self.assertEqual(reply.routing_trace.get("slot"), "room")
        self.assertIn("exactement", reply.answer.lower())

    def test_weather_missing_city_triggers_clarification(self) -> None:
        reply = handle_message("meteo", use_leon_fallback=True, conversation_id="conv-4")
        self.assertEqual(reply.source, "local-clarification")
        self.assertEqual(reply.intent, "weather")
        self.assertEqual(reply.routing_trace.get("slot"), "city")

    def test_weather_followup_city_resolves(self) -> None:
        first = handle_message("meteo", use_leon_fallback=True, conversation_id="conv-5")
        self.assertEqual(first.source, "local-clarification")

        second = handle_message("a paris", use_leon_fallback=True, conversation_id="conv-5")
        self.assertEqual(second.source, "local")
        self.assertEqual(second.intent, "weather")
        self.assertEqual(second.routing_trace.get("reason"), "clarification_resolved")
        self.assertIn("paris", second.answer)

    @patch("src.assistant.orchestrator.LeonClient")
    def test_repeated_failures_open_circuit(self, mock_leon_cls: Any) -> None:
        LEON_CIRCUIT_BREAKER.failure_threshold = 2
        LEON_CIRCUIT_BREAKER.cooldown_seconds = 60.0
        mock_leon: Any = mock_leon_cls.from_env.return_value
        mock_leon.ask.return_value = None

        first = handle_message("question inconnue 1", use_leon_fallback=True)
        second = handle_message("question inconnue 2", use_leon_fallback=True)
        third = handle_message("question inconnue 3", use_leon_fallback=True)

        self.assertEqual(first.source, "fallback-error")
        self.assertEqual(second.source, "fallback-error")
        self.assertEqual(third.routing_trace.get("reason"), "circuit_open")

    @patch("src.assistant.orchestrator.LeonClient")
    def test_success_resets_circuit_breaker(self, mock_leon_cls: Any) -> None:
        LEON_CIRCUIT_BREAKER.failure_threshold = 2
        LEON_CIRCUIT_BREAKER.cooldown_seconds = 60.0
        mock_leon: Any = mock_leon_cls.from_env.return_value
        mock_leon.ask.side_effect = [None, "Reponse Leon"]

        first = handle_message("question inconnue 1", use_leon_fallback=True)
        second = handle_message("question inconnue 2", use_leon_fallback=True)

        self.assertEqual(first.source, "fallback-error")
        self.assertEqual(second.source, "leon")
        self.assertEqual(LEON_CIRCUIT_BREAKER.consecutive_failures, 0)


if __name__ == "__main__":
    unittest.main()
