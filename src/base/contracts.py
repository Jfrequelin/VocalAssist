from __future__ import annotations

import base64
from dataclasses import dataclass
from time import time
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class EdgeAudioRequest:
    correlation_id: str
    device_id: str
    timestamp_ms: int
    sample_rate_hz: int
    channels: int
    encoding: str
    audio_base64: str

    @classmethod
    def from_audio_bytes(
        cls,
        *,
        audio_bytes: bytes,
        device_id: str,
        sample_rate_hz: int,
        channels: int,
        encoding: str,
        correlation_id: str | None = None,
    ) -> "EdgeAudioRequest":
        if not audio_bytes:
            raise ValueError("audio_bytes ne peut pas etre vide")
        if not device_id.strip():
            raise ValueError("device_id ne peut pas etre vide")

        return cls(
            correlation_id=correlation_id or str(uuid4()),
            device_id=device_id.strip(),
            timestamp_ms=int(time() * 1000),
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            encoding=encoding,
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
        )

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


@dataclass(frozen=True)
class EdgeAudioResponse:
    status_code: int
    payload: dict[str, Any] | None

    @property
    def accepted(self) -> bool:
        return 200 <= self.status_code < 300 and isinstance(self.payload, dict)
