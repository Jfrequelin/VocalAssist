from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SpeechToTextEngine(Protocol):
    def transcribe(self, audio_payload: str) -> str: ...


class TextToSpeechEngine(Protocol):
    def synthesize(self, text: str) -> str: ...


@dataclass
class MockSpeechToText:
    """Simulation STT: la charge audio est deja du texte."""

    def transcribe(self, audio_payload: str) -> str:
        return audio_payload.strip()


@dataclass
class MockTextToSpeech:
    """Simulation TTS: renvoie simplement le texte de sortie."""

    def synthesize(self, text: str) -> str:
        return text
