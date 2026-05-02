from __future__ import annotations

import argparse
import json
from typing import Any, cast
from http.server import BaseHTTPRequestHandler, HTTPServer


class LeonMockHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "leon-mock"})
            return
        self._send_json(404, {"status": "error", "reason": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/query":
            self._send_json(404, {"status": "error", "reason": "not_found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"status": "error", "reason": "invalid_json"})
            return

        payload_map = cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
        query = str(payload_map.get("query", "")).strip()
        answer = f"[LEON_MOCK] Reponse a: {query or 'requete vide'}"
        self._send_json(200, {"answer": answer})


def main() -> None:
    parser = argparse.ArgumentParser(description="Leon mock HTTP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=1337)
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), LeonMockHandler)
    print(f"[leon-mock] Listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
