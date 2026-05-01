from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeBaseConfig:
    device_id: str
    server_base_url: str
    endpoint: str = "/edge/audio"
    wake_word: str = "nova"
    sample_rate_hz: int = 16000
    channels: int = 1
    encoding: str = "pcm16le"
    min_voice_chars: int = 6
    timeout_seconds: float = 3.0
    retry_attempts: int = 2
    retry_backoff_seconds: float = 0.2

    def validate(self) -> None:
        if not self.device_id.strip():
            raise ValueError("device_id ne peut pas etre vide")
        if not self.server_base_url.strip():
            raise ValueError("server_base_url ne peut pas etre vide")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz doit etre > 0")
        if self.channels <= 0:
            raise ValueError("channels doit etre > 0")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds doit etre > 0")
        if self.retry_attempts < 0:
            raise ValueError("retry_attempts doit etre >= 0")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds doit etre >= 0")
