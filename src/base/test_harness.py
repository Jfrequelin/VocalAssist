from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import EdgeBaseConfig
from .contracts import EdgeAudioRequest, EdgeAudioResponse
from .interfaces import Playback, TransportClient
from .peripherals import CapturedAudio, MicrophoneDevice, ScreenDevice, SpeakerDevice
from .runtime import EdgeRuntime, RuntimeResult


@dataclass(frozen=True)
class ExchangeRecord:
    transcript: str
    runtime_result: RuntimeResult
    request_payload: dict[str, Any] | None
    response_payload: dict[str, Any] | None


class RecordingTransport:
    """Decorator transport that records the last assistant exchange payloads."""

    def __init__(self, transport: TransportClient) -> None:
        self._transport = transport
        self.last_request: EdgeAudioRequest | None = None
        self.last_response: EdgeAudioResponse | None = None

    def send_audio(self, request: EdgeAudioRequest) -> EdgeAudioResponse:
        self.last_request = request
        self.last_response = self._transport.send_audio(request)
        return self.last_response


class DeviceSpeakerPlayback(Playback):
    def __init__(self, speaker: SpeakerDevice) -> None:
        self._speaker = speaker

    def play_text(self, text: str) -> None:
        self._speaker.play(text)


class StaticMicrophoneBuffer:
    """Deterministic microphone stub feeding predefined audio captures."""

    def __init__(self, captured: list[CapturedAudio]) -> None:
        self._captured = list(captured)

    def capture(self) -> CapturedAudio | None:
        if not self._captured:
            return None
        return self._captured.pop(0)


class AssistantFirmwareTestBench:
    """Base de test firmware avec peripheriques abstraits.

    Ce harness execute le runtime edge (firmware local) et enregistre
    l'echange avec l'assistant serveur selon le contrat audio v2.
    """

    def __init__(
        self,
        *,
        config: EdgeBaseConfig,
        transport: TransportClient,
        microphone: MicrophoneDevice,
        speaker: SpeakerDevice,
        screen: ScreenDevice,
    ) -> None:
        self._screen = screen
        self._microphone = microphone
        self._recording_transport = RecordingTransport(transport)
        self._runtime = EdgeRuntime(
            config=config,
            transport=self._recording_transport,
            playback=DeviceSpeakerPlayback(speaker),
        )

    def set_mute(self, enabled: bool) -> None:
        self._runtime.set_mute(enabled)
        state = self._runtime.state_machine.runtime.state.value
        self._screen.show(state=state, message=f"mute={enabled}")

    def run_once(self) -> ExchangeRecord | None:
        captured = self._microphone.capture()
        if captured is None:
            self._screen.show(state="idle", message="capture_stopped")
            return None

        transcript = captured.transcript
        self._screen.show(state="listening", message=f"heard={transcript}")
        result = self._runtime.process_audio(
            transcript=transcript,
            audio_bytes=captured.audio_bytes,
        )

        current_state = self._runtime.state_machine.runtime.state.value
        self._screen.show(state=current_state, message=f"result={result.reason}")

        request_payload = None
        if self._recording_transport.last_request is not None:
            request_payload = self._recording_transport.last_request.to_dict()

        response_payload = None
        if self._recording_transport.last_response is not None:
            response_payload = self._recording_transport.last_response.payload

        return ExchangeRecord(
            transcript=transcript,
            runtime_result=result,
            request_payload=request_payload,
            response_payload=response_payload,
        )

    def run_until_stop(self, *, max_turns: int | None = None) -> list[ExchangeRecord]:
        exchanges: list[ExchangeRecord] = []
        turns = 0
        while True:
            record = self.run_once()
            if record is None:
                break
            exchanges.append(record)
            turns += 1
            if max_turns is not None and turns >= max_turns:
                break
        return exchanges
