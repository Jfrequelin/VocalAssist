from __future__ import annotations

import json
import os
from time import sleep
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from urllib import error, request


# Contrat d'appel Leon
# Requete JSON envoyee:
# {
#   "query": "<message utilisateur>"
# }
#
# Formats de reponse supportes:
# - string brute
# - {"answer": "..."} ou {"output": "..."} ou {"response": "..."} ou {"text": "..."}
# - {"data": {"answer"|"output"|"text": "..."}}
# - {"answers": ["...", ...]} ou {"messages": ["...", ...]}
#
# En cas d'erreur reseau/timeout/format invalide: retourne None.


@dataclass
class LeonClient:
    base_url: str
    endpoint: str = "/api/query"
    timeout_seconds: float = 5.0
    retry_attempts: int = 1
    retry_backoff_seconds: float = 0.0

    @classmethod
    def from_env(cls) -> "LeonClient":
        base_url = os.getenv("LEON_API_URL", "http://localhost:1337")
        endpoint = os.getenv("LEON_API_ENDPOINT", "/api/query")
        timeout = float(os.getenv("LEON_TIMEOUT_SECONDS", "5"))
        retry_attempts = int(os.getenv("LEON_RETRY_ATTEMPTS", "1"))
        retry_backoff = float(os.getenv("LEON_RETRY_BACKOFF_SECONDS", "0"))
        return cls(
            base_url=base_url.rstrip("/"),
            endpoint=endpoint,
            timeout_seconds=timeout,
            retry_attempts=max(0, retry_attempts),
            retry_backoff_seconds=max(0.0, retry_backoff),
        )

    def ask(self, message: str) -> str | None:
        payload = json.dumps({"query": message}).encode("utf-8")
        url = f"{self.base_url}{self.endpoint}"
        req = request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        attempts = self.retry_attempts + 1
        raw: str | None = None
        for attempt in range(attempts):
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                break
            except (error.URLError, TimeoutError, ValueError, OSError):
                if attempt + 1 >= attempts:
                    return None
                if self.retry_backoff_seconds > 0:
                    sleep(self.retry_backoff_seconds)

        if raw is None:
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
        return self._extract_from_map(body_map)

    def _extract_from_map(self, body_map: dict[str, Any]) -> str | None:
        direct = self._pick_text(
            [
                body_map.get("answer"),
                body_map.get("output"),
                body_map.get("response"),
                body_map.get("text"),
            ]
        )
        if direct is not None:
            return direct

        data = body_map.get("data")
        if isinstance(data, Mapping):
            data_map = cast(dict[str, Any], data)
            nested = self._pick_text([data_map.get("answer"), data_map.get("output"), data_map.get("text")])
            if nested is not None:
                return nested

        for key in ["answers", "messages"]:
            values = body_map.get(key)
            from_list = self._extract_from_list(values)
            if from_list is not None:
                return from_list

        return None

    def _extract_from_list(self, values: Any) -> str | None:
        if not isinstance(values, list):
            return None

        items = cast(list[Any], values)
        for item in items:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    return text

            if isinstance(item, Mapping):
                item_map = cast(dict[str, Any], item)
                nested = self._pick_text([item_map.get("text")])
                if nested is not None:
                    return nested

        return None

    def _pick_text(self, candidates: list[Any]) -> str | None:
        for candidate in candidates:
            if isinstance(candidate, str):
                text = candidate.strip()
                if text:
                    return text
        return None
