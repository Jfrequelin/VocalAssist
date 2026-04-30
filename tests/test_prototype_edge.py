from __future__ import annotations

import unittest
from unittest.mock import patch

from src.assistant.edge_device import EdgeDeviceController
from src.assistant.prototype_edge import _handle_control_command, _process_audio_segment
from src.assistant.voice_pipeline import MockTextToSpeech


class TestPrototypeEdgeControlCommands(unittest.TestCase):
    def test_status_command_returns_true(self) -> None:
        controller = EdgeDeviceController()
        with patch("builtins.print") as mock_print:
            handled = _handle_control_command("/status", controller)
        self.assertTrue(handled)
        self.assertTrue(mock_print.called)

    def test_mute_and_unmute_commands(self) -> None:
        controller = EdgeDeviceController()

        self.assertTrue(_handle_control_command("/mute", controller))
        self.assertTrue(controller.state.muted)
        self.assertEqual(controller.state.led_state, "muted")

        self.assertTrue(_handle_control_command("/unmute", controller))
        self.assertFalse(controller.state.muted)

    def test_button_command_cuts_interaction(self) -> None:
        controller = EdgeDeviceController()
        controller.start_interaction()

        with patch("builtins.print"):
            handled = _handle_control_command("/button", controller)

        self.assertTrue(handled)
        self.assertFalse(controller.state.interaction_active)
        self.assertEqual(controller.state.last_event, "button_pressed")

    def test_unknown_control_command_returns_false(self) -> None:
        controller = EdgeDeviceController()
        handled = _handle_control_command("/noop", controller)
        self.assertFalse(handled)


class TestPrototypeEdgeProcessAudioSegment(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = EdgeDeviceController()
        self.tts = MockTextToSpeech()

    @patch("src.assistant.prototype_edge.send_edge_audio_payload")
    @patch("src.assistant.prototype_edge.build_edge_audio_payload")
    def test_process_audio_segment_speaks_when_unmuted(self, mock_build, mock_send) -> None:
        mock_build.return_value = object()
        mock_send.return_value = {"correlation_id": "cid-1", "received_bytes": 12}

        with patch("builtins.print") as mock_print:
            _process_audio_segment(
                raw="nova allume la lumiere",
                wake_word="nova",
                device_id="esp32-1",
                base_url="http://localhost:8081",
                retry_attempts=1,
                retry_backoff_seconds=0.0,
                controller=self.controller,
                tts=self.tts,
            )

        printed = "\n".join(call.args[0] for call in mock_print.call_args_list if call.args)
        self.assertIn("Edge(TTS): Payload accepte", printed)
        self.assertEqual(self.controller.state.last_event, "interaction_finished")
        self.assertFalse(self.controller.state.interaction_active)

    @patch("src.assistant.prototype_edge.send_edge_audio_payload")
    @patch("src.assistant.prototype_edge.build_edge_audio_payload")
    def test_process_audio_segment_respects_mute(self, mock_build, mock_send) -> None:
        mock_build.return_value = object()
        mock_send.return_value = {"correlation_id": "cid-2", "received_bytes": 10}
        self.controller.set_mute(True)

        with patch("builtins.print") as mock_print:
            _process_audio_segment(
                raw="nova donne la meteo",
                wake_word="nova",
                device_id="esp32-1",
                base_url="http://localhost:8081",
                retry_attempts=1,
                retry_backoff_seconds=0.0,
                controller=self.controller,
                tts=self.tts,
            )

        printed = "\n".join(call.args[0] for call in mock_print.call_args_list if call.args)
        self.assertIn("Edge(TTS): muet, restitution audio supprimee", printed)

    @patch("src.assistant.prototype_edge.send_edge_audio_payload")
    def test_process_audio_segment_backend_failure_sets_error_state(self, mock_send) -> None:
        mock_send.return_value = None

        with patch("builtins.print") as mock_print:
            _process_audio_segment(
                raw="nova test",
                wake_word="nova",
                device_id="esp32-1",
                base_url="http://localhost:8081",
                retry_attempts=1,
                retry_backoff_seconds=0.0,
                controller=self.controller,
                tts=self.tts,
            )

        printed = "\n".join(call.args[0] for call in mock_print.call_args_list if call.args)
        self.assertIn("Edge: envoi echoue ou reponse invalide du backend", printed)
        self.assertEqual(self.controller.state.last_event, "interaction_error")

    @patch("src.assistant.prototype_edge.send_edge_audio_payload")
    @patch("src.assistant.prototype_edge.build_edge_audio_payload")
    def test_process_audio_segment_ignores_non_activated_input(self, mock_build, mock_send) -> None:
        with patch("builtins.print") as mock_print:
            _process_audio_segment(
                raw="bruit ambiant",
                wake_word="nova",
                device_id="esp32-1",
                base_url="http://localhost:8081",
                retry_attempts=1,
                retry_backoff_seconds=0.0,
                controller=self.controller,
                tts=self.tts,
            )

        mock_build.assert_not_called()
        mock_send.assert_not_called()
        printed = "\n".join(call.args[0] for call in mock_print.call_args_list if call.args)
        self.assertIn("Edge: segment ignore", printed)


if __name__ == "__main__":
    unittest.main()
