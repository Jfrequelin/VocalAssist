from __future__ import annotations

from typing import Protocol

from .contracts import EdgeAudioRequest, EdgeAudioResponse


class TransportClient(Protocol):
    def send_audio(self, request: EdgeAudioRequest) -> EdgeAudioResponse: ...


class Playback(Protocol):
    def play_text(self, text: str) -> None: ...
