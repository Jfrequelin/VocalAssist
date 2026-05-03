from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import Mock
from unittest.mock import patch

from src.base.peripherals import LinuxArecordMicrophoneAdapter, LinuxSystemSpeakerAdapter


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
            playback_binary="/usr/bin/aplay",
        )

        captured = adapter.capture()

        self.assertIsNotNone(captured)
        if captured is None:
            return
        self.assertEqual(captured.transcript, "quit")
        self.assertEqual(captured.audio_bytes, b"quit")

    @patch("src.base.peripherals.subprocess.run")
    @patch("builtins.input", return_value="")
    def test_capture_replays_audio_when_enabled(self, _input: Any, mock_run: Any) -> None:
        mock_run.return_value.returncode = 0
        adapter = LinuxArecordMicrophoneAdapter(
            transcribe=lambda _path: "nova test",
            arecord_binary="/usr/bin/arecord",
            playback_binary="/usr/bin/aplay",
            replay_capture=True,
        )

        captured = adapter.capture()

        self.assertIsNotNone(captured)
        calls = [call.args[0] for call in mock_run.call_args_list if call.args]
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "/usr/bin/arecord")
        self.assertEqual(calls[1][0], "/usr/bin/aplay")

    @patch("src.base.peripherals.subprocess.run")
    @patch("builtins.input", return_value="")
    def test_capture_uses_configured_alsa_device(self, _input: Any, mock_run: Any) -> None:
        mock_run.return_value.returncode = 0
        adapter = LinuxArecordMicrophoneAdapter(
            transcribe=lambda _path: "nova test",
            arecord_binary="/usr/bin/arecord",
            capture_device="hw:CARD=Generic_1,DEV=0",
            replay_capture=False,
        )

        captured = adapter.capture()

        self.assertIsNotNone(captured)
        calls = [call.args[0] for call in mock_run.call_args_list if call.args]
        self.assertGreaterEqual(len(calls), 1)
        self.assertIn("-D", calls[0])
        self.assertIn("hw:CARD=Generic_1,DEV=0", calls[0])

    @patch("src.base.peripherals.subprocess.run")
    @patch("builtins.input", return_value="")
    def test_capture_falls_back_to_stereo_when_mono_is_unsupported(self, _input: Any, mock_run: Any) -> None:
        first = Mock()
        first.returncode = 1
        first.stderr = "arecord: set_params:1398: Nombre de canaux non disponible"
        second = Mock()
        second.returncode = 0
        second.stderr = ""
        third = Mock()
        third.returncode = 0
        third.stderr = ""
        mock_run.side_effect = [first, second, third]

        adapter = LinuxArecordMicrophoneAdapter(
            transcribe=lambda _path: "nova test",
            arecord_binary="/usr/bin/arecord",
            playback_binary="/usr/bin/aplay",
            channels=1,
            sample_rate_hz=16000,
            replay_capture=True,
        )

        captured = adapter.capture()

        self.assertIsNotNone(captured)
        calls = [call.args[0] for call in mock_run.call_args_list if call.args]
        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(calls[0][0], "/usr/bin/arecord")
        self.assertIn("-c", calls[0])
        self.assertIn("1", calls[0])
        self.assertEqual(calls[1][0], "/usr/bin/arecord")
        self.assertIn("-c", calls[1])
        self.assertIn("2", calls[1])


class TestLinuxSystemSpeakerAdapter(unittest.TestCase):
    @patch.dict(os.environ, {"ASSISTANT_TTS_ENGINE": "spd-say", "ASSISTANT_TTS_WARMUP": "true"}, clear=False)
    @patch("src.base.peripherals.subprocess.run")
    @patch("src.base.peripherals.shutil.which")
    def test_spd_say_warmup_runs_once(self, mock_which: Any, mock_run: Any) -> None:
        mock_which.side_effect = ["/usr/bin/spd-say", "/usr/bin/espeak"]

        adapter = LinuxSystemSpeakerAdapter()
        adapter.play("assistant vocal")
        adapter.play("deuxieme message")

        calls = [call.args[0] for call in mock_run.call_args_list if call.args]
        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(calls[0], ["/usr/bin/spd-say", "-w", " "])
        self.assertEqual(calls[1], ["/usr/bin/spd-say", "-w", "assistant vocal"])
        self.assertEqual(calls[2], ["/usr/bin/spd-say", "-w", "deuxieme message"])

    @patch.dict(os.environ, {"ASSISTANT_TTS_ENGINE": "espeak"}, clear=False)
    @patch("src.base.peripherals.subprocess.run")
    @patch("src.base.peripherals.shutil.which")
    def test_engine_override_espeak(self, mock_which: Any, mock_run: Any) -> None:
        mock_which.side_effect = ["/usr/bin/spd-say", "/usr/bin/espeak"]

        adapter = LinuxSystemSpeakerAdapter()
        adapter.play("assistant vocal")

        calls = [call.args[0] for call in mock_run.call_args_list if call.args]
        self.assertEqual(calls[0], ["/usr/bin/espeak", "-v", "fr", "assistant vocal"])


if __name__ == "__main__":
    unittest.main()
