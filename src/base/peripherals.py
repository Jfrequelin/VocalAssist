from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CapturedAudio:
    transcript: str
    audio_bytes: bytes


class MicrophoneDevice(Protocol):
    def capture(self) -> CapturedAudio | None: ...


class SpeakerDevice(Protocol):
    def play(self, text: str) -> None: ...


class ScreenDevice(Protocol):
    def show(self, *, state: str, message: str) -> None: ...


class StdinMicrophoneAdapter:
    """Desktop adapter: uses keyboard input to simulate microphone capture."""

    def __init__(self, *, prompt: str = "Audio brut(simule): ") -> None:
        self._prompt = prompt

    def capture(self) -> CapturedAudio | None:
        raw = input(self._prompt).strip()
        if raw.lower() in {"quit", "exit", "stop"}:
            return None
        if not raw:
            return CapturedAudio(transcript="", audio_bytes=b"")
        return CapturedAudio(transcript=raw, audio_bytes=raw.encode("utf-8"))


class ConsoleSpeakerAdapter:
    """Desktop adapter: redirects spoken text to console output."""

    def __init__(self) -> None:
        self.played_messages: list[str] = []

    def play(self, text: str) -> None:
        self.played_messages.append(text)
        print(f"Speaker: {text}")


class MockScreenAdapter:
    """Mock screen used by tests to assert UI-like state transitions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def show(self, *, state: str, message: str) -> None:
        self.events.append((state, message))


class ConsoleScreenAdapter:
    """Desktop adapter: shows simplified device UI state in console."""

    def show(self, *, state: str, message: str) -> None:
        print(f"Screen[{state}]: {message}")
