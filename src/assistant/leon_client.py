from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from urllib import error, request


@dataclass
class LeonClient:
    base_url: str
    endpoint: str = "/api/query"
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "LeonClient":
        base_url = os.getenv("LEON_API_URL", "http://localhost:1337")
        endpoint = os.getenv("LEON_API_ENDPOINT", "/api/query")
        timeout = float(os.getenv("LEON_TIMEOUT_SECONDS", "5"))
        return cls(base_url=base_url.rstrip("/"), endpoint=endpoint, timeout_seconds=timeout)

    def ask(self, message: str) -> str | None:
        payload = json.dumps({"query": message}).encode("utf-8")
        url = f"{self.base_url}{self.endpoint}"
        req = request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (error.URLError, TimeoutError, ValueError):
            return None

        try:
            body: Any = json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip() or None

        return self._extract_text(body)

    def _extract_text(self, body: Any) -> str | None:
        if isinstance(body, str):
            return body.strip() or None

        if not isinstance(body, Mapping):
            return None

        body_map = cast(dict[str, Any], body)

        # Supporte plusieurs formats de reponse potentiels selon version Leon.
        candidates = [
            body_map.get("answer"),
            body_map.get("output"),
            body_map.get("response"),
            body_map.get("text"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        data = body_map.get("data")
        if isinstance(data, Mapping):
            data_map = cast(dict[str, Any], data)
            nested = [data_map.get("answer"), data_map.get("output"), data_map.get("text")]
            for candidate in nested:
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

        return None
