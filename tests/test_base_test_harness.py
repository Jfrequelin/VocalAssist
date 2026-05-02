from __future__ import annotations

import unittest

from src.base import AssistantFirmwareTestBench, EdgeAudioResponse, EdgeBaseConfig
from src.base.contracts import EdgeAudioRequest
from src.base.peripherals import CapturedAudio, MockScreenAdapter
from src.base.test_harness import StaticMicrophoneBuffer


class _TransportOk:
    def send_audio(self, request: EdgeAudioRequest) -> EdgeAudioResponse:
        return EdgeAudioResponse(
            status_code=200,
            payload={
                "status": "accepted",
                "api_version": "v2",
                "correlation_id": request.correlation_id,
                "reply": "Il est 08:42.",
                "answer": "Il est 08:42.",
            },
        )


class _TransportRejected:
    def send_audio(self, request: EdgeAudioRequest) -> EdgeAudioResponse:
        return EdgeAudioResponse(status_code=400, payload={"status": "error", "reason": "invalid_payload"})


class _SpeakerSpy:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def play(self, text: str) -> None:
        self.messages.append(text)


class TestAssistantFirmwareTestBench(unittest.TestCase):
    def test_records_exchange_in_v2_shape(self) -> None:
        config = EdgeBaseConfig(device_id="edge-01", server_base_url="http://127.0.0.1:8081")
        microphone = StaticMicrophoneBuffer(
            [
                CapturedAudio(
                    transcript="nova quelle heure est-il",
                    audio_bytes=b"dummy-audio",
                )
            ]
        )
        speaker = _SpeakerSpy()
        screen = MockScreenAdapter()

        bench = AssistantFirmwareTestBench(
            config=config,
            transport=_TransportOk(),
            microphone=microphone,
            speaker=speaker,
            screen=screen,
        )

        record = bench.run_once()

        self.assertIsNotNone(record)
        if record is None:
            return
        self.assertTrue(record.runtime_result.sent)
        self.assertEqual(record.runtime_result.reason, "accepted")
        self.assertIsNotNone(record.request_payload)
        self.assertIsNotNone(record.response_payload)
        if record.request_payload is None or record.response_payload is None:
            return

        self.assertEqual(record.request_payload["device_id"], "edge-01")
        self.assertEqual(record.request_payload["encoding"], "pcm16le")
        self.assertIn("correlation_id", record.request_payload)
        self.assertEqual(record.response_payload["status"], "accepted")
        self.assertEqual(record.response_payload["api_version"], "v2")

        self.assertEqual(speaker.messages, ["Il est 08:42."])
        self.assertGreaterEqual(len(screen.events), 2)

    def test_rejects_without_wake_word_and_does_not_send(self) -> None:
        config = EdgeBaseConfig(device_id="edge-01", server_base_url="http://127.0.0.1:8081")
        microphone = StaticMicrophoneBuffer(
            [CapturedAudio(transcript="quelle heure est-il", audio_bytes=b"dummy-audio")]
        )
        speaker = _SpeakerSpy()
        screen = MockScreenAdapter()

        bench = AssistantFirmwareTestBench(
            config=config,
            transport=_TransportOk(),
            microphone=microphone,
            speaker=speaker,
            screen=screen,
        )

        record = bench.run_once()

        self.assertIsNotNone(record)
        if record is None:
            return
        self.assertFalse(record.runtime_result.sent)
        self.assertEqual(record.runtime_result.reason, "wake_word_missing")
        self.assertIsNone(record.request_payload)
        self.assertEqual(speaker.messages, [])

    def test_backend_rejection_is_returned(self) -> None:
        config = EdgeBaseConfig(device_id="edge-01", server_base_url="http://127.0.0.1:8081")
        microphone = StaticMicrophoneBuffer([CapturedAudio(transcript="nova test", audio_bytes=b"dummy-audio")])
        speaker = _SpeakerSpy()
        screen = MockScreenAdapter()

        bench = AssistantFirmwareTestBench(
            config=config,
            transport=_TransportRejected(),
            microphone=microphone,
            speaker=speaker,
            screen=screen,
        )

        record = bench.run_once()

        self.assertIsNotNone(record)
        if record is None:
            return
        self.assertFalse(record.runtime_result.sent)
        self.assertEqual(record.runtime_result.reason, "backend_rejected")
        self.assertIsNotNone(record.response_payload)

    def test_control_commands_do_not_send_backend_payload(self) -> None:
        config = EdgeBaseConfig(device_id="edge-01", server_base_url="http://127.0.0.1:8081")
        microphone = StaticMicrophoneBuffer([CapturedAudio(transcript="/mute", audio_bytes=b"")])
        speaker = _SpeakerSpy()
        screen = MockScreenAdapter()

        bench = AssistantFirmwareTestBench(
            config=config,
            transport=_TransportOk(),
            microphone=microphone,
            speaker=speaker,
            screen=screen,
        )

        record = bench.run_once()

        self.assertIsNotNone(record)
        if record is None:
            return
        self.assertFalse(record.runtime_result.sent)
        self.assertEqual(record.runtime_result.reason, "control_mute_on")
        self.assertIsNone(record.request_payload)
        self.assertIsNone(record.response_payload)


if __name__ == "__main__":
    unittest.main()
