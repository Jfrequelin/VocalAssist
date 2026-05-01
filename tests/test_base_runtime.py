from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast

from src.base import AssistantEdgeTransport, EdgeBaseConfig, EdgeRuntime
from src.base.contracts import EdgeAudioResponse


class _FakeTransport:
    def __init__(self, response: EdgeAudioResponse) -> None:
        self._response = response

    def send_audio(self, request):  # type: ignore[no-untyped-def]
        return self._response


class _CollectPlayback:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def play_text(self, text: str) -> None:
        self.messages.append(text)


class TestBaseRuntime(unittest.TestCase):
    def test_runtime_rejects_without_wake_word(self) -> None:
        config = EdgeBaseConfig(device_id="esp32-base-01", server_base_url="http://127.0.0.1:8081")
        runtime = EdgeRuntime(
            config=config,
            transport=_FakeTransport(EdgeAudioResponse(status_code=200, payload={"status": "accepted"})),
        )

        result = runtime.process_audio(transcript="quelle heure est il", audio_bytes=b"abc")

        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "wake_word_missing")

    def test_runtime_sends_and_plays_reply(self) -> None:
        config = EdgeBaseConfig(device_id="esp32-base-01", server_base_url="http://127.0.0.1:8081")
        playback = _CollectPlayback()
        runtime = EdgeRuntime(
            config=config,
            transport=_FakeTransport(
                EdgeAudioResponse(status_code=200, payload={"status": "accepted", "reply": "Bonjour"})
            ),
            playback=playback,
        )

        result = runtime.process_audio(transcript="nova quelle heure est il", audio_bytes=b"edge")

        self.assertTrue(result.sent)
        self.assertEqual(result.reason, "accepted")
        self.assertIsNotNone(result.correlation_id)
        self.assertEqual(playback.messages, ["Bonjour"])

    def test_transport_calls_edge_audio_endpoint(self) -> None:
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                self.server.hit_count += 1  # type: ignore[attr-defined]
                self.server.last_path = self.path  # type: ignore[attr-defined]

                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length)
                payload = json.loads(raw.decode("utf-8"))

                body = json.dumps(
                    {
                        "status": "accepted",
                        "correlation_id": payload.get("correlation_id", "missing"),
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        server.hit_count = 0  # type: ignore[attr-defined]
        server.last_path = ""  # type: ignore[attr-defined]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            host, port = cast(tuple[str, int], server.server_address)
            config = EdgeBaseConfig(
                device_id="esp32-base-01",
                server_base_url=f"http://{host}:{port}",
            )
            transport = AssistantEdgeTransport(config)
            runtime = EdgeRuntime(config=config, transport=transport)

            result = runtime.process_audio(transcript="nova lance test", audio_bytes=b"payload")

            self.assertTrue(result.sent)
            self.assertEqual(server.hit_count, 1)  # type: ignore[attr-defined]
            self.assertEqual(server.last_path, "/edge/audio")  # type: ignore[attr-defined]
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
