from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.assistant.base_testbench import InProcessEdgeBackendTransport, build_microphone, build_screen, build_transport
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
    def test_auto_screen_falls_back_to_console_when_tk_unavailable(self, _mock_tk) -> None:  # type: ignore[no-untyped-def]
        with patch.dict(os.environ, {"ASSISTANT_TESTBENCH_SCREEN": "auto"}, clear=False):
            screen = build_screen()

        self.assertIsInstance(screen, ConsoleScreenAdapter)


if __name__ == "__main__":
    unittest.main()
