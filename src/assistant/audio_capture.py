from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioCaptureConfig:
    sample_rate_hz: int = 16000
    channels: int = 1
    encoding: str = "pcm16le"
    chunk_size_bytes: int = 640
    max_buffer_chunks: int = 50


@dataclass(frozen=True)
class AudioCaptureStats:
    buffered_chunks: int
    buffered_bytes: int
    dropped_chunks: int


class CircularAudioBuffer:
    """Circular buffer for edge audio capture resilience."""

    def __init__(self, config: AudioCaptureConfig | None = None) -> None:
        self._config = config or AudioCaptureConfig()
        self._chunks: deque[bytes] = deque(maxlen=self._config.max_buffer_chunks)
        self._dropped_chunks = 0

    @property
    def config(self) -> AudioCaptureConfig:
        return self._config

    def push_chunk(self, chunk: bytes) -> None:
        if not chunk:
            return

        if len(chunk) > self._config.chunk_size_bytes:
            # Keep the most recent tail to preserve realtime behavior.
            chunk = chunk[-self._config.chunk_size_bytes :]

        if len(self._chunks) == self._chunks.maxlen:
            self._dropped_chunks += 1
        self._chunks.append(chunk)

    def drain(self) -> bytes:
        if not self._chunks:
            return b""

        merged = b"".join(self._chunks)
        self._chunks.clear()
        return merged

    def stats(self) -> AudioCaptureStats:
        buffered_bytes = sum(len(chunk) for chunk in self._chunks)
        return AudioCaptureStats(
            buffered_chunks=len(self._chunks),
            buffered_bytes=buffered_bytes,
            dropped_chunks=self._dropped_chunks,
        )
