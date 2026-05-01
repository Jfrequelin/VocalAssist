from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BaseState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    SENDING = "sending"
    SPEAKING = "speaking"
    MUTED = "muted"
    ERROR = "error"


@dataclass
class RuntimeState:
    state: BaseState = BaseState.IDLE
    muted: bool = False
    last_event: str = "init"


class EdgeStateMachine:
    def __init__(self) -> None:
        self._runtime = RuntimeState()

    @property
    def runtime(self) -> RuntimeState:
        return self._runtime

    def set_mute(self, enabled: bool) -> None:
        self._runtime.muted = enabled
        self._runtime.state = BaseState.MUTED if enabled else BaseState.IDLE
        self._runtime.last_event = "mute_on" if enabled else "mute_off"

    def start_listening(self) -> None:
        if self._runtime.muted:
            self._runtime.last_event = "listen_skipped_muted"
            return
        self._runtime.state = BaseState.LISTENING
        self._runtime.last_event = "listening_started"

    def mark_sending(self) -> None:
        if self._runtime.muted:
            self._runtime.last_event = "send_skipped_muted"
            return
        self._runtime.state = BaseState.SENDING
        self._runtime.last_event = "audio_sending"

    def mark_speaking(self) -> None:
        if self._runtime.muted:
            self._runtime.last_event = "speak_skipped_muted"
            return
        self._runtime.state = BaseState.SPEAKING
        self._runtime.last_event = "response_speaking"

    def mark_error(self, reason: str) -> None:
        self._runtime.state = BaseState.ERROR
        self._runtime.last_event = f"error:{reason}"

    def back_to_idle(self) -> None:
        self._runtime.state = BaseState.MUTED if self._runtime.muted else BaseState.IDLE
        self._runtime.last_event = "interaction_finished"
