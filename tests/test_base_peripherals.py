from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from src.base.peripherals import LinuxArecordMicrophoneAdapter


class TestLinuxArecordMicrophoneAdapter(unittest.TestCase):
    @patch("src.base.peripherals.subprocess.run")
    @patch("builtins.input", return_value="quit")
    def test_capture_stops_on_explicit_keyboard_quit(self, _input: Any, _run: Any) -> None:
        adapter = LinuxArecordMicrophoneAdapter(
            transcribe=lambda _path: "nova quelle heure est-il",
            arecord_binary="/usr/bin/arecord",
        )

        captured = adapter.capture()

        self.assertIsNone(captured)

    @patch("src.base.peripherals.subprocess.run")
    @patch("builtins.input", return_value="")
    def test_capture_does_not_stop_on_transcribed_quit(self, _input: Any, mock_run: Any) -> None:
        mock_run.return_value.returncode = 0
        adapter = LinuxArecordMicrophoneAdapter(
            transcribe=lambda _path: "quit",
            arecord_binary="/usr/bin/arecord",
        )

        captured = adapter.capture()

        self.assertIsNotNone(captured)
        if captured is None:
            return
        self.assertEqual(captured.transcript, "quit")
        self.assertEqual(captured.audio_bytes, b"quit")


if __name__ == "__main__":
    unittest.main()
