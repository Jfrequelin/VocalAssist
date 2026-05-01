from __future__ import annotations

from dataclasses import dataclass

from .config import EdgeBaseConfig
from .contracts import EdgeAudioRequest
from .interfaces import Playback, TransportClient
from .state_machine import EdgeStateMachine


@dataclass(frozen=True)
class RuntimeResult:
    sent: bool
    reason: str
    correlation_id: str | None = None


class EdgeRuntime:
    def __init__(
        self,
        *,
        config: EdgeBaseConfig,
        transport: TransportClient,
        playback: Playback | None = None,
        state_machine: EdgeStateMachine | None = None,
    ) -> None:
        config.validate()
        self._config = config
        self._transport = transport
        self._playback = playback
        self._state_machine = state_machine or EdgeStateMachine()

    @property
    def state_machine(self) -> EdgeStateMachine:
        return self._state_machine

    def set_mute(self, enabled: bool) -> None:
        self._state_machine.set_mute(enabled)

    def process_audio(self, *, transcript: str, audio_bytes: bytes) -> RuntimeResult:
        cleaned = transcript.strip().lower()
        if self._state_machine.runtime.muted:
            return RuntimeResult(sent=False, reason="muted")

        self._state_machine.start_listening()
        decision = self._evaluate_activation(cleaned)
        if decision is not None:
            self._state_machine.back_to_idle()
            return RuntimeResult(sent=False, reason=decision)

        self._state_machine.mark_sending()
        request_payload = EdgeAudioRequest.from_audio_bytes(
            audio_bytes=audio_bytes,
            device_id=self._config.device_id,
            sample_rate_hz=self._config.sample_rate_hz,
            channels=self._config.channels,
            encoding=self._config.encoding,
        )

        response = self._transport.send_audio(request_payload)
        if not response.accepted:
            self._state_machine.mark_error("backend_rejected")
            return RuntimeResult(
                sent=False,
                reason="backend_rejected",
                correlation_id=request_payload.correlation_id,
            )

        reply_text = _extract_reply_text(response.payload)
        if reply_text and self._playback is not None:
            self._state_machine.mark_speaking()
            self._playback.play_text(reply_text)

        self._state_machine.back_to_idle()
        return RuntimeResult(sent=True, reason="accepted", correlation_id=request_payload.correlation_id)

    def _evaluate_activation(self, transcript: str) -> str | None:
        if not transcript:
            return "empty_audio"

        alnum_count = sum(1 for ch in transcript if ch.isalnum())
        if alnum_count < self._config.min_voice_chars:
            return "vad_rejected_low_voice"

        wake_word = self._config.wake_word.lower().strip()
        if not transcript.startswith(wake_word):
            return "wake_word_missing"

        command = transcript[len(wake_word) :].strip()
        if not command:
            return "wake_word_without_command"

        return None


def _extract_reply_text(payload: dict[str, object] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    reply = payload.get("reply")
    if isinstance(reply, str):
        return reply.strip()
    return ""
