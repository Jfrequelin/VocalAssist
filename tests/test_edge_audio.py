from __future__ import annotations

import json
import threading
import unittest
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast
from unittest.mock import patch

from src.assistant.edge_audio import (
    EdgeAudioPayload,
    attenuate_pcm16le,
    build_edge_audio_payload,
    evaluate_edge_activation,
    sanitize_pcm16le_if_saturated,
    send_edge_audio_payload,
    saturation_ratio_pcm16le,
)
from src.assistant.edge_backend import handle_edge_audio_request


class TestEdgeAudio(unittest.TestCase):
    def test_edge_activation_rejects_ambient_noise(self) -> None:
        decision = evaluate_edge_activation("...", wake_word="nova")
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "vad_rejected_low_voice")

    def test_edge_activation_rejects_missing_wake_word(self) -> None:
        decision = evaluate_edge_activation("quelle heure est il", wake_word="nova")
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "wake_word_missing")

    def test_edge_activation_accepts_command_after_wake_word(self) -> None:
        decision = evaluate_edge_activation("nova quelle heure est il", wake_word="nova")
        self.assertTrue(decision.should_send)
        self.assertEqual(decision.reason, "accepted")
        self.assertEqual(decision.command, "quelle heure est il")

    def test_edge_activation_wake_word_is_case_insensitive(self) -> None:
        decision = evaluate_edge_activation("NoVa quelle heure est il", wake_word="NOVA")
        self.assertTrue(decision.should_send)
        self.assertEqual(decision.reason, "accepted")
        self.assertEqual(decision.command, "quelle heure est il")

    def test_edge_activation_rejects_noise_profile_after_wake_word(self) -> None:
        decision = evaluate_edge_activation("nova aaaa aaaa aaaa", wake_word="nova")
        self.assertFalse(decision.should_send)
        self.assertEqual(decision.reason, "vad_rejected_noise_profile")

    def test_build_payload_encodes_audio(self) -> None:
        payload = build_edge_audio_payload(b"abc", device_id="esp32-01", correlation_id="cid-1")
        self.assertEqual(payload.correlation_id, "cid-1")
        self.assertEqual(payload.device_id, "esp32-01")
        self.assertEqual(payload.audio_base64, "YWJj")

    def test_saturation_ratio_detects_clipping(self) -> None:
        saturated = (32767).to_bytes(2, "little", signed=True) * 10
        ratio = saturation_ratio_pcm16le(saturated)
        self.assertEqual(ratio, 1.0)

    def test_attenuation_reduces_pcm_amplitude(self) -> None:
        sample = (20000).to_bytes(2, "little", signed=True)
        attenuated = attenuate_pcm16le(sample, factor=0.5)
        value = int.from_bytes(attenuated, "little", signed=True)
        self.assertLess(value, 20000)
        self.assertGreater(value, 0)

    def test_attenuation_rejects_odd_length_pcm(self) -> None:
        with self.assertRaises(ValueError):
            attenuate_pcm16le(b"\x01\x02\x03", factor=0.8)

    def test_build_payload_applies_auto_attenuation_when_saturated(self) -> None:
        saturated = (32767).to_bytes(2, "little", signed=True) * 32
        payload = build_edge_audio_payload(
            saturated,
            device_id="esp32-01",
            correlation_id="cid-sat",
            encoding="pcm16le",
        )
        decoded = base64.b64decode(payload.audio_base64.encode("ascii"), validate=True)
        self.assertNotEqual(decoded, saturated)

    def test_sanitize_skips_non_pcm16le_encoding(self) -> None:
        raw = b"abc123"
        sanitized, ratio, applied = sanitize_pcm16le_if_saturated(raw, encoding="wav")
        self.assertEqual(sanitized, raw)
        self.assertEqual(ratio, 0.0)
        self.assertFalse(applied)

    def test_sanitize_skips_odd_length_pcm_payload(self) -> None:
        raw = b"\x01\x02\x03"
        sanitized, ratio, applied = sanitize_pcm16le_if_saturated(raw, encoding="pcm16le")
        self.assertEqual(sanitized, raw)
        self.assertEqual(ratio, 0.0)
        self.assertFalse(applied)

    def test_backend_accepts_valid_payload(self) -> None:
        payload = EdgeAudioPayload(
            correlation_id="cid-2",
            device_id="esp32-01",
            timestamp_ms=123,
            sample_rate_hz=16000,
            channels=1,
            encoding="pcm16le",
            audio_base64="cXVlbGxlIGhldXJlIGVzdCBpbA==",
        )
        status, response = handle_edge_audio_request(json.dumps(payload.to_dict()).encode("utf-8"))

        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "accepted")
        self.assertEqual(response["api_version"], "v2")
        self.assertEqual(response["correlation_id"], "cid-2")
        self.assertEqual(response["intent"], "time")
        self.assertEqual(response["source"], "local")
        self.assertIn("Il est", response["answer"])

    def test_backend_rejects_invalid_payload(self) -> None:
        status, response = handle_edge_audio_request(b"{}")
        self.assertEqual(status, 400)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["api_version"], "v2")

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
                b"quelle heure est il", device_id="esp32-edge", correlation_id="cid-loop"
            )
            response = send_edge_audio_payload(payload, base_url=f"http://{host}:{port}")
            self.assertIsNotNone(response)
            if response is None:
                return
            self.assertEqual(response.get("status"), "accepted")
            self.assertEqual(response.get("correlation_id"), "cid-loop")
            self.assertEqual(response.get("intent"), "time")
            self.assertEqual(response.get("source"), "local")
            self.assertIn("Il est", str(response.get("answer")))
        finally:
            server.shutdown()
            server.server_close()

    def test_send_retries_and_eventually_succeeds(self) -> None:
        attempts = {"count": 0}

        class _FlakyHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                attempts["count"] += 1
                if attempts["count"] == 1:
                    self.send_response(503)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length)
                status, response = handle_edge_audio_request(raw)
                body = json.dumps(response).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), _FlakyHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = cast(tuple[str, int], server.server_address)
            payload = build_edge_audio_payload(b"quelle heure est il", device_id="esp32-edge")
            response = send_edge_audio_payload(
                payload,
                base_url=f"http://{host}:{port}",
                retry_attempts=2,
                retry_backoff_seconds=0.0,
            )
            self.assertIsNotNone(response)
            self.assertEqual(attempts["count"], 2)
        finally:
            server.shutdown()
            server.server_close()

    def test_send_returns_none_when_backend_down(self) -> None:
        payload = build_edge_audio_payload(b"edge-audio", device_id="esp32-edge")
        response = send_edge_audio_payload(
            payload,
            base_url="http://127.0.0.1:9",
            timeout_seconds=0.05,
            retry_attempts=1,
            retry_backoff_seconds=0.0,
        )
        self.assertIsNone(response)

    def test_backend_rejects_non_utf8_audio(self) -> None:
        payload = EdgeAudioPayload(
            correlation_id="cid-bad",
            device_id="esp32-01",
            timestamp_ms=123,
            sample_rate_hz=16000,
            channels=1,
            encoding="pcm16le",
            audio_base64="//4=",
        )
        status, response = handle_edge_audio_request(json.dumps(payload.to_dict()).encode("utf-8"))

        self.assertEqual(status, 400)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["reason"], "invalid_pcm_frame")

    def test_backend_rejects_unsupported_encoding(self) -> None:
        payload = EdgeAudioPayload(
            correlation_id="cid-enc",
            device_id="esp32-01",
            timestamp_ms=123,
            sample_rate_hz=16000,
            channels=1,
            encoding="wav",
            audio_base64="cXVlbGxlIGhldXJlIGVzdCBpbA==",
        )

        status, response = handle_edge_audio_request(json.dumps(payload.to_dict()).encode("utf-8"))

        self.assertEqual(status, 400)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["reason"], "unsupported_encoding")

    def test_backend_accepts_utf8_encoding(self) -> None:
        payload = EdgeAudioPayload(
            correlation_id="cid-utf8",
            device_id="esp32-01",
            timestamp_ms=123,
            sample_rate_hz=16000,
            channels=1,
            encoding="utf8",
            audio_base64="cXVlbGxlIGhldXJlIGVzdCBpbA==",
        )

        status, response = handle_edge_audio_request(json.dumps(payload.to_dict()).encode("utf-8"))

        self.assertEqual(status, 200)
        self.assertEqual(response["status"], "accepted")

    def test_backend_rejects_pcm_text_proxy_when_disabled(self) -> None:
        payload = EdgeAudioPayload(
            correlation_id="cid-pcm-off",
            device_id="esp32-01",
            timestamp_ms=123,
            sample_rate_hz=16000,
            channels=1,
            encoding="pcm16le",
            audio_base64="cXVlbGxlIGhldXJlIGVzdCBpbA==",
        )

        with patch.dict("os.environ", {"EDGE_BACKEND_ALLOW_TEXT_PROXY": "false"}, clear=False):
            status, response = handle_edge_audio_request(json.dumps(payload.to_dict()).encode("utf-8"))

        self.assertEqual(status, 400)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["reason"], "unsupported_encoding")

    def test_backend_rejects_odd_length_pcm_frame(self) -> None:
        payload = EdgeAudioPayload(
            correlation_id="cid-pcm-odd",
            device_id="esp32-01",
            timestamp_ms=123,
            sample_rate_hz=16000,
            channels=1,
            encoding="pcm16le",
            audio_base64="AQID",
        )

        status, response = handle_edge_audio_request(json.dumps(payload.to_dict()).encode("utf-8"))

        self.assertEqual(status, 400)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["api_version"], "v2")
        self.assertEqual(response["reason"], "invalid_pcm_frame")


if __name__ == "__main__":
    unittest.main()
