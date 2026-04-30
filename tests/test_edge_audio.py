from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast

from src.assistant.edge_audio import (
    EdgeAudioPayload,
    build_edge_audio_payload,
    send_edge_audio_payload,
)
from src.assistant.edge_backend import handle_edge_audio_request


class TestEdgeAudio(unittest.TestCase):
    def test_build_payload_encodes_audio(self) -> None:
        payload = build_edge_audio_payload(b"abc", device_id="esp32-01", correlation_id="cid-1")
        self.assertEqual(payload.correlation_id, "cid-1")
        self.assertEqual(payload.device_id, "esp32-01")
        self.assertEqual(payload.audio_base64, "YWJj")

    def test_backend_accepts_valid_payload(self) -> None:
        payload = EdgeAudioPayload(
            correlation_id="cid-2",
            device_id="esp32-01",
            timestamp_ms=123,
            sample_rate_hz=16000,
            channels=1,
            encoding="pcm16le",
            audio_base64="YWJj",
        )
        status, response = handle_edge_audio_request(json.dumps(payload.to_dict()).encode("utf-8"))

        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "accepted")
        self.assertEqual(response["correlation_id"], "cid-2")

    def test_backend_rejects_invalid_payload(self) -> None:
        status, response = handle_edge_audio_request(b"{}")
        self.assertEqual(status, 400)
        self.assertEqual(response["status"], "error")

    def test_edge_to_backend_loop(self) -> None:
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length)
                status, response = handle_edge_audio_request(raw)
                body = json.dumps(response).encode("utf-8")

                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = cast(tuple[str, int], server.server_address)
            payload = build_edge_audio_payload(
                b"edge-audio", device_id="esp32-edge", correlation_id="cid-loop"
            )
            response = send_edge_audio_payload(payload, base_url=f"http://{host}:{port}")
            self.assertIsNotNone(response)
            if response is None:
                return
            self.assertEqual(response.get("status"), "accepted")
            self.assertEqual(response.get("correlation_id"), "cid-loop")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
