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
        self._wake_word = config.wake_word.strip().lower()
        self._awaiting_followup_command = False
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
        # Reset recordings to avoid carrying previous exchange payloads.
        self._recording_transport.last_request = None
        self._recording_transport.last_response = None

        if transcript.startswith("/"):
            self._awaiting_followup_command = False
            return self._handle_control_command(transcript)

        effective_transcript = transcript
        if (
            self._awaiting_followup_command
            and transcript.strip()
            and not transcript.strip().lower().startswith(self._wake_word)
        ):
            effective_transcript = f"{self._wake_word} {transcript.strip()}"

        self._screen.show(state="listening", message=f"heard={effective_transcript}")
        result = self._runtime.process_audio(
            transcript=effective_transcript,
            audio_bytes=captured.audio_bytes,
        )

        if result.reason == "wake_word_without_command":
            self._awaiting_followup_command = True
            self._screen.show(state="listening", message="wake_word_ok: en attente de commande")
        elif result.reason != "empty_audio":
            self._awaiting_followup_command = False

        current_state = self._runtime.state_machine.runtime.state.value
        self._screen.show(state=current_state, message=f"result={result.reason}")

        request_payload = None
        if self._recording_transport.last_request is not None:
            request_payload = self._recording_transport.last_request.to_dict()

        response_payload = None
        if self._recording_transport.last_response is not None:
            response_payload = self._recording_transport.last_response.payload

        return ExchangeRecord(
            transcript=effective_transcript,
            runtime_result=result,
            request_payload=request_payload,
            response_payload=response_payload,
        )

    def _handle_control_command(self, transcript: str) -> ExchangeRecord:
        command = transcript.strip().lower()
        if command == "/mute":
            self.set_mute(True)
            reason = "control_mute_on"
        elif command == "/unmute":
            self.set_mute(False)
            reason = "control_mute_off"
        elif command == "/status":
            current = self._runtime.state_machine.runtime
            self._screen.show(state=current.state.value, message=f"muted={current.muted}, event={current.last_event}")
            reason = "control_status"
        else:
            self._screen.show(state="idle", message="controls: /help /status /mute /unmute")
            reason = "control_help"

        result = RuntimeResult(sent=False, reason=reason)
        return ExchangeRecord(
            transcript=transcript,
            runtime_result=result,
            request_payload=None,
            response_payload=None,
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
