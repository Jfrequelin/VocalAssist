from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, cast

from src.assistant.orchestrator import handle_message

REQUIRED_FIELDS = {
    "correlation_id",
    "device_id",
    "timestamp_ms",
    "sample_rate_hz",
    "channels",
    "encoding",
    "audio_base64",
}


def validate_edge_audio_payload(payload: Mapping[str, Any]) -> str | None:
    missing = REQUIRED_FIELDS - set(payload.keys())
    if missing:
        return f"missing_fields:{','.join(sorted(missing))}"

    if not isinstance(payload.get("correlation_id"), str) or not payload["correlation_id"].strip():
        return "invalid_correlation_id"
    if not isinstance(payload.get("device_id"), str) or not payload["device_id"].strip():
        return "invalid_device_id"
    if not isinstance(payload.get("sample_rate_hz"), int) or payload["sample_rate_hz"] <= 0:
        return "invalid_sample_rate"
    if not isinstance(payload.get("channels"), int) or payload["channels"] <= 0:
        return "invalid_channels"
    if not isinstance(payload.get("encoding"), str) or not payload["encoding"].strip():
        return "invalid_encoding"

    audio_base64 = payload.get("audio_base64")
    if not isinstance(audio_base64, str) or not audio_base64.strip():
        return "invalid_audio_base64"

    try:
        decoded = base64.b64decode(audio_base64.encode("ascii"), validate=True)
    except (ValueError, binascii.Error):
        return "invalid_audio_base64"

    if not decoded:
        return "empty_audio"

    return None


def handle_edge_audio_request(raw_body: bytes) -> tuple[int, dict[str, Any]]:
    try:
        parsed: Any = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"status": "error", "reason": "invalid_json"}

    if not isinstance(parsed, Mapping):
        return 400, {"status": "error", "reason": "invalid_payload_type"}

    payload = dict(cast(Mapping[str, Any], parsed))
    validation_error = validate_edge_audio_payload(payload)
    if validation_error:
        return 400, {"status": "error", "reason": validation_error}

    audio_bytes = base64.b64decode(str(payload["audio_base64"]).encode("ascii"), validate=True)
    try:
        command = audio_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        return 400, {"status": "error", "reason": "invalid_audio_utf8"}

    if not command:
        return 400, {"status": "error", "reason": "empty_command"}

    # Enable Leon fallback for unknown intents; if not configured, returns default fallback answer
    reply = handle_message(
        command,
        use_leon_fallback=True,
        correlation_id=str(payload["correlation_id"]),
    )
    return 200, {
        "status": "accepted",
        "correlation_id": str(payload["correlation_id"]),
        "received_bytes": len(audio_bytes),
        "intent": reply.intent,
        "source": reply.source,
        "answer": reply.answer,
    }


class EdgeAudioRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/edge/audio":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        status_code, response = handle_edge_audio_request(raw_body)

        body = json.dumps(response).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_edge_backend_server(host: str = "127.0.0.1", port: int = 8081) -> None:
    server = HTTPServer((host, port), EdgeAudioRequestHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
