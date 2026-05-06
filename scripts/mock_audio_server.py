#!/usr/bin/env python3
"""
Mock audio server minimal pour tester l'envoi son de la base ESP32.

Endpoints:
- GET  /health
- POST /edge/audio

Contrat compatible firmware:
- Reçoit JSON avec audio_base64 + meta
- Répond 202 avec audio_base64 (echo + gain) et champs v2

Usage:
  python3 scripts/mock_audio_server.py [port]
"""

from __future__ import annotations

import base64
import json
import math
import struct
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

START_TIME = time.time()
DEFAULT_PORT = 8080


def make_tone_pcm16(sr: int = 16000, hz: int = 660, duration_ms: int = 700, amp: int = 12000) -> bytes:
    samples = max(1, int(sr * duration_ms / 1000))
    out = bytearray(samples * 2)
    for i in range(samples):
        v = int(amp * math.sin(2.0 * math.pi * hz * (i / sr)))
        out[2 * i : 2 * i + 2] = struct.pack("<h", v)
    return bytes(out)


def apply_gain_pcm16(pcm: bytes, gain: float = 2.0) -> bytes:
    if not pcm:
        return pcm
    samples = len(pcm) // 2
    values = struct.unpack(f"<{samples}h", pcm[: samples * 2])
    boosted = []
    for s in values:
        v = int(s * gain)
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        boosted.append(v)
    return struct.pack(f"<{samples}h", *boosted)


class Handler(BaseHTTPRequestHandler):
    server_version = "AssistantVocalMock/1.0"

    def _send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args) -> None:
        now = time.strftime("%H:%M:%S")
        print(f"[{now}] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_json(404, {"error": "not_found"})
            return
        self._send_json(
            200,
            {
                "ok": True,
                "version": "mock-audio-1.0.0",
                "uptime_s": int(time.time() - START_TIME),
            },
        )

    def do_POST(self) -> None:
        if self.path != "/edge/audio":
            self._send_json(404, {"error": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json(400, {"status": "error", "reason": "invalid_json"})
            return

        cid = str(payload.get("correlation_id", ""))
        encoding = str(payload.get("encoding", "pcm16le"))
        sr = int(payload.get("sample_rate_hz", 16000))
        channels = int(payload.get("channels", 1))
        audio_b64 = str(payload.get("audio_base64", ""))

        received_bytes = 0
        duration_ms = 0

        out_pcm = b""
        if audio_b64:
            try:
                in_pcm = base64.b64decode(audio_b64)
                received_bytes = len(in_pcm)
                samples = received_bytes // 2
                duration_ms = int(samples / max(sr, 1) * 1000)
                out_pcm = apply_gain_pcm16(in_pcm, gain=2.0)
                print(
                    f"[AUDIO] cid={cid} bytes={received_bytes} duration_ms={duration_ms} -> echo+gain"
                )
            except Exception:
                out_pcm = make_tone_pcm16()
        else:
            out_pcm = make_tone_pcm16()

        response = {
            "status": "accepted",
            "api_version": "v2",
            "correlation_id": cid,
            "received_bytes": received_bytes,
            "duration_ms": duration_ms,
            "encoding": encoding,
            "sample_rate_hz": sr,
            "channels": channels,
            "audio_base64": base64.b64encode(out_pcm).decode("ascii"),
            "intent": "mock_audio",
            "answer": f"Mock OK: {received_bytes} bytes recus",
        }
        self._send_json(202, response)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    print(f"Mock audio server listening on 0.0.0.0:{port}")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()
