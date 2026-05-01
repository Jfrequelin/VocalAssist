from __future__ import annotations

import json
from time import sleep
from urllib import error, request
from typing import cast

from .config import EdgeBaseConfig
from .contracts import EdgeAudioRequest, EdgeAudioResponse


class AssistantEdgeTransport:
    def __init__(self, config: EdgeBaseConfig) -> None:
        config.validate()
        self._config = config

    def send_audio(self, request: EdgeAudioRequest) -> EdgeAudioResponse:
        url = f"{self._config.server_base_url.rstrip('/')}{self._config.endpoint}"
        body = json.dumps(request.to_dict()).encode("utf-8")
        attempts = self._config.retry_attempts + 1

        for idx in range(attempts):
            response = self._post_once(url=url, body=body)
            should_retry = response.status_code >= 500 or response.status_code == 429
            if not should_retry:
                return response
            if idx + 1 < attempts and self._config.retry_backoff_seconds > 0:
                sleep(self._config.retry_backoff_seconds)

        return EdgeAudioResponse(status_code=503, payload={"status": "error", "reason": "retry_exhausted"})

    def _post_once(self, *, url: str, body: bytes) -> EdgeAudioResponse:
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self._config.timeout_seconds) as raw:
                raw_body = raw.read().decode("utf-8")
                payload = _parse_json_dict(raw_body)
                return EdgeAudioResponse(status_code=int(raw.status), payload=payload)
        except error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            return EdgeAudioResponse(status_code=exc.code, payload=_parse_json_dict(raw_body))
        except (error.URLError, TimeoutError, ValueError):
            return EdgeAudioResponse(status_code=503, payload={"status": "error", "reason": "network_unavailable"})


def _parse_json_dict(raw: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return cast(dict[str, object], parsed)
    return None
