from __future__ import annotations

import os
import tempfile
import unittest
from typing import Any
from unittest.mock import patch

from src.assistant.base_testbench import (
    InProcessEdgeBackendTransport,
    TestbenchMetrics,
    apply_silence_backoff,
    build_microphone,
    build_session_snapshot,
    build_screen,
    build_transport,
    format_metrics_line,
    maybe_export_snapshot,
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

    def test_timeline_event_is_recorded(self) -> None:
        metrics = TestbenchMetrics()

        update_metrics(
            metrics,
            sent=True,
            reason="accepted",
            latency_ms=11.2,
            response_payload={"status": "accepted", "intent": "time", "source": "local"},
        )

        self.assertIsNotNone(metrics.timeline)
        if metrics.timeline is None:
            return
        self.assertEqual(len(metrics.timeline), 1)
        self.assertEqual(metrics.timeline[0].get("reason"), "accepted")
        self.assertEqual(metrics.timeline[0].get("intent"), "time")

    def test_export_snapshot_writes_json_when_path_configured(self) -> None:
        metrics = TestbenchMetrics(total_turns=1, sent_turns=1, total_latency_ms=9.0)
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "snapshot.json")
            with patch.dict(os.environ, {"ASSISTANT_TESTBENCH_EXPORT_PATH": target}, clear=False):
                exported = maybe_export_snapshot(metrics)

            self.assertEqual(exported, target)
            self.assertTrue(os.path.exists(target))

    def test_build_session_snapshot_contains_summary_and_timeline(self) -> None:
        metrics = TestbenchMetrics(total_turns=2, sent_turns=1, rejected_turns=1, total_latency_ms=40.0)
        metrics.timeline = [{"reason": "accepted"}, {"reason": "wake_word_missing"}]

        snapshot = build_session_snapshot(metrics)

        self.assertIn("summary", snapshot)
        self.assertIn("timeline", snapshot)
        self.assertEqual(len(snapshot["timeline"]), 2)

    @patch("src.assistant.base_testbench.sleep")
    def test_apply_silence_backoff_waits_for_empty_audio(self, mock_sleep: Any) -> None:
        waited = apply_silence_backoff(reason="empty_audio", wait_seconds=5.0)

        self.assertTrue(waited)
        mock_sleep.assert_called_once_with(5.0)

    @patch("src.assistant.base_testbench.sleep")
    def test_apply_silence_backoff_skips_for_non_silence(self, mock_sleep: Any) -> None:
        waited = apply_silence_backoff(reason="accepted", wait_seconds=5.0)

        self.assertFalse(waited)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
