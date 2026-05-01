from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass
from time import sleep
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

    if _is_noise_like_text(command, min_voice_chars=min_voice_chars):
        return EdgeActivationDecision(should_send=False, reason="vad_rejected_noise_profile")

    return EdgeActivationDecision(should_send=True, reason="accepted", command=command)


def _is_noise_like_text(text: str, min_voice_chars: int) -> bool:
    """Reject highly non-verbal commands that pass basic char count."""
    compact = text.strip()
    if not compact:
        return True

    non_space_count = sum(1 for ch in compact if not ch.isspace())
    if non_space_count == 0:
        return True

    punctuation_count = sum(1 for ch in compact if not ch.isalnum() and not ch.isspace())
    if punctuation_count / non_space_count > 0.60:
        return True

    alpha_chars = [ch for ch in compact if ch.isalpha()]
    if len(alpha_chars) >= min_voice_chars and len(set(alpha_chars)) <= 2:
        return True

    return False


def build_edge_audio_payload(
    audio_bytes: bytes,
    device_id: str,
    correlation_id: str | None = None,
    sample_rate_hz: int = 16000,
    channels: int = 1,
    encoding: str = "pcm16le",
    auto_attenuate_saturation: bool = True,
    saturation_threshold: float = 0.08,
    attenuation_factor: float = 0.8,
) -> EdgeAudioPayload:
    if not audio_bytes:
        raise ValueError("audio_bytes ne peut pas etre vide")
    if not device_id.strip():
        raise ValueError("device_id ne peut pas etre vide")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz doit etre > 0")
    if channels <= 0:
        raise ValueError("channels doit etre > 0")

    prepared_audio = audio_bytes
    if auto_attenuate_saturation:
        prepared_audio, _, _ = sanitize_pcm16le_if_saturated(
            audio_bytes,
            encoding=encoding,
            saturation_threshold=saturation_threshold,
            attenuation_factor=attenuation_factor,
        )

    encoded = base64.b64encode(prepared_audio).decode("ascii")
    return EdgeAudioPayload(
        correlation_id=correlation_id or str(uuid4()),
        device_id=device_id.strip(),
        timestamp_ms=int(time() * 1000),
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        encoding=encoding,
        audio_base64=encoded,
    )


def saturation_ratio_pcm16le(audio_bytes: bytes, *, sample_limit: int = 32760) -> float:
    """Estimate clipping ratio on 16-bit PCM audio."""
    if sample_limit <= 0:
        raise ValueError("sample_limit doit etre > 0")

    sample_count = len(audio_bytes) // 2
    if sample_count == 0:
        return 0.0

    clipped = 0
    view = memoryview(audio_bytes)
    for idx in range(sample_count):
        sample = struct.unpack_from("<h", view, idx * 2)[0]
        if abs(sample) >= sample_limit:
            clipped += 1

    return clipped / sample_count


def attenuate_pcm16le(audio_bytes: bytes, *, factor: float = 0.8) -> bytes:
    if factor <= 0:
        raise ValueError("factor doit etre > 0")

    sample_count = len(audio_bytes) // 2
    if sample_count == 0:
        return audio_bytes

    out = bytearray(sample_count * 2)
    view = memoryview(audio_bytes)
    for idx in range(sample_count):
        sample = struct.unpack_from("<h", view, idx * 2)[0]
        scaled = int(sample * factor)
        scaled = max(-32768, min(32767, scaled))
        struct.pack_into("<h", out, idx * 2, scaled)

    if len(audio_bytes) % 2 == 1:
        out.extend(audio_bytes[-1:])

    return bytes(out)


def sanitize_pcm16le_if_saturated(
    audio_bytes: bytes,
    *,
    encoding: str,
    saturation_threshold: float = 0.08,
    attenuation_factor: float = 0.8,
) -> tuple[bytes, float, bool]:
    normalized_encoding = encoding.strip().lower()
    if normalized_encoding not in {"pcm16le", "pcm_s16le"}:
        return audio_bytes, 0.0, False

    ratio = saturation_ratio_pcm16le(audio_bytes)
    if ratio < saturation_threshold:
        return audio_bytes, ratio, False

    return attenuate_pcm16le(audio_bytes, factor=attenuation_factor), ratio, True


def send_edge_audio_payload(
    payload: EdgeAudioPayload,
    base_url: str,
    endpoint: str = "/edge/audio",
    timeout_seconds: float = 3.0,
    retry_attempts: int = 1,
    retry_backoff_seconds: float = 0.0,
) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}{endpoint}"
    body = json.dumps(payload.to_dict()).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    attempts = max(0, retry_attempts) + 1
    raw: str | None = None
    for idx in range(attempts):
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            break
        except (error.URLError, TimeoutError, ValueError):
            if idx + 1 >= attempts:
                return None
            if retry_backoff_seconds > 0:
                sleep(retry_backoff_seconds)

    if raw is None:
        return None

    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return cast(dict[str, Any], parsed)
    return None
