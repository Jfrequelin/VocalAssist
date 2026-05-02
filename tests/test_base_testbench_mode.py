from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import patch

from src.assistant.base_testbench import (
    InProcessEdgeBackendTransport,
    TestbenchMetrics,
    build_microphone,
    build_screen,
    build_transport,
    format_metrics_line,
    summarize_turn,
    update_metrics,
)
from src.base import ConsoleScreenAdapter, EdgeAudioRequest, EdgeBaseConfig
from src.base.peripherals import StdinMicrophoneAdapter


class TestBaseTestbenchMode(unittest.TestCase):
    def test_build_transport_local_uses_in_process_backend(self) -> None:
        config = EdgeBaseConfig(device_id="edge-01", server_base_url="http://127.0.0.1:8081")
        with patch.dict(os.environ, {"ASSISTANT_TESTBENCH_TRANSPORT": "local"}, clear=False):
            transport = build_transport(config)

        self.assertIsInstance(transport, InProcessEdgeBackendTransport)

    def test_in_process_transport_handles_valid_request(self) -> None:
        transport = InProcessEdgeBackendTransport()
        request = EdgeAudioRequest.from_audio_bytes(
            audio_bytes=b"quelle heure est il",
            device_id="edge-01",
            sample_rate_hz=16000,
            channels=1,
            encoding="pcm16le",
            correlation_id="cid-testbench",
        )

        response = transport.send_audio(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.payload)
        if response.payload is None:
            return
        self.assertEqual(response.payload.get("status"), "accepted")
        self.assertEqual(response.payload.get("api_version"), "v2")

    def test_mock_peripherals_mode_keeps_stdin_adapter(self) -> None:
        config = EdgeBaseConfig(device_id="edge-01", server_base_url="http://127.0.0.1:8081")
        with patch.dict(os.environ, {"ASSISTANT_TESTBENCH_PERIPHERALS": "mock"}, clear=False):
            mic = build_microphone(config)

        self.assertIsInstance(mic, StdinMicrophoneAdapter)

    @patch("src.assistant.base_testbench.TkScreenAdapter", side_effect=RuntimeError("headless"))
    def test_auto_screen_falls_back_to_console_when_tk_unavailable(self, _mock_tk: Any) -> None:
        with patch.dict(os.environ, {"ASSISTANT_TESTBENCH_SCREEN": "auto"}, clear=False):
            screen = build_screen()

        self.assertIsInstance(screen, ConsoleScreenAdapter)

    def test_update_metrics_tracks_turn_outcomes(self) -> None:
        metrics = TestbenchMetrics()

        update_metrics(
            metrics,
            sent=True,
            reason="accepted",
            latency_ms=12.5,
            response_payload={"intent": "time", "source": "local", "status": "accepted"},
        )
        update_metrics(
            metrics,
            sent=False,
            reason="backend_rejected",
            latency_ms=20.0,
            response_payload={"status": "error"},
        )

        self.assertEqual(metrics.total_turns, 2)
        self.assertEqual(metrics.sent_turns, 1)
        self.assertEqual(metrics.rejected_turns, 1)
        self.assertEqual(metrics.backend_errors, 1)
        self.assertEqual(metrics.last_intent, "time")
        self.assertEqual(metrics.last_source, "local")
        self.assertAlmostEqual(metrics.avg_latency_ms, 16.25)

    def test_summaries_include_latency_intent_source(self) -> None:
        metrics = TestbenchMetrics(total_turns=3, sent_turns=2, rejected_turns=1, total_latency_ms=42.0)
        turn_summary = summarize_turn(
            reason="accepted",
            latency_ms=14.0,
            response_payload={"status": "accepted", "intent": "weather", "source": "local"},
        )
        metrics_line = format_metrics_line(metrics)

        self.assertIn("reason=accepted", turn_summary)
        self.assertIn("intent=weather", turn_summary)
        self.assertIn("source=local", turn_summary)
        self.assertIn("avg_latency_ms=14.0", metrics_line)


if __name__ == "__main__":
    unittest.main()
