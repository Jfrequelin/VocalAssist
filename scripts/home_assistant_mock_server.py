from __future__ import annotations

import argparse
import json
from typing import Any, cast
from http.server import BaseHTTPRequestHandler, HTTPServer


class HomeAssistantMockHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "ha-mock"})
            return
        self._send_json(404, {"status": "error", "reason": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._send_json(401, {"status": "error", "reason": "missing_bearer_token"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"status": "error", "reason": "invalid_json"})
            return

        if not isinstance(payload, dict):
            self._send_json(400, {"status": "error", "reason": "invalid_payload"})
            return

        payload_map = cast(dict[str, Any], payload)

        entity_id = str(payload_map.get("entity_id", "")).strip()
        if not entity_id:
            self._send_json(400, {"status": "error", "reason": "missing_entity_id"})
            return

        allowed_paths = {
            "/api/services/light/turn_on",
            "/api/services/light/turn_off",
            "/api/services/scene/turn_on",
            "/api/services/climate/set_temperature",
        }
        if self.path not in allowed_paths:
            self._send_json(404, {"status": "error", "reason": "not_found"})
            return

        response: dict[str, object] = {
            "status": "ok",
            "path": self.path,
            "entity_id": entity_id,
        }
        if self.path == "/api/services/climate/set_temperature":
            response["temperature"] = payload_map.get("temperature")

        self._send_json(200, response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Home Assistant mock HTTP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), HomeAssistantMockHandler)
    print(f"[ha-mock] Listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
