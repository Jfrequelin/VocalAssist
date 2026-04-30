from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from time import time
from typing import Any, cast
from urllib import error, request
from uuid import uuid4


@dataclass
class EdgeAudioPayload:
    correlation_id: str
    device_id: str
    timestamp_ms: int
    sample_rate_hz: int
    channels: int
    encoding: str
    audio_base64: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "device_id": self.device_id,
            "timestamp_ms": self.timestamp_ms,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "encoding": self.encoding,
            "audio_base64": self.audio_base64,
        }


@dataclass
class EdgeActivationDecision:
    should_send: bool
    reason: str
    command: str = ""


def evaluate_edge_activation(
    transcript: str,
    wake_word: str = "nova",
    min_voice_chars: int = 6,
) -> EdgeActivationDecision:
    text = transcript.strip().lower()
    if not text:
        return EdgeActivationDecision(should_send=False, reason="empty_audio")

    # VAD heuristique minimal: rejette les segments tres courts/non verbaux.
    alnum_count = sum(1 for ch in text if ch.isalnum())
    if alnum_count < min_voice_chars:
        return EdgeActivationDecision(should_send=False, reason="vad_rejected_low_voice")

    if not text.startswith(wake_word):
        return EdgeActivationDecision(should_send=False, reason="wake_word_missing")

    command = text[len(wake_word) :].strip()
    if not command:
        return EdgeActivationDecision(should_send=False, reason="wake_word_without_command")

    return EdgeActivationDecision(should_send=True, reason="accepted", command=command)


def build_edge_audio_payload(
    audio_bytes: bytes,
    device_id: str,
    correlation_id: str | None = None,
    sample_rate_hz: int = 16000,
    channels: int = 1,
    encoding: str = "pcm16le",
) -> EdgeAudioPayload:
    if not audio_bytes:
        raise ValueError("audio_bytes ne peut pas etre vide")
    if not device_id.strip():
        raise ValueError("device_id ne peut pas etre vide")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz doit etre > 0")
    if channels <= 0:
        raise ValueError("channels doit etre > 0")

    encoded = base64.b64encode(audio_bytes).decode("ascii")
    return EdgeAudioPayload(
        correlation_id=correlation_id or str(uuid4()),
        device_id=device_id.strip(),
        timestamp_ms=int(time() * 1000),
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        encoding=encoding,
        audio_base64=encoded,
    )


def send_edge_audio_payload(
    payload: EdgeAudioPayload,
    base_url: str,
    endpoint: str = "/edge/audio",
    timeout_seconds: float = 3.0,
) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}{endpoint}"
    body = json.dumps(payload.to_dict()).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except (error.URLError, TimeoutError, ValueError):
        return None

    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)
    return None
