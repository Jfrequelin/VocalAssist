from __future__ import annotations

import unittest
from typing import Any
from urllib import error
from unittest.mock import patch

from src.assistant.leon_client import LeonClient


class _FakeResponse:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


class TestLeonClient(unittest.TestCase):
    def test_ask_supports_standard_answer_format(self) -> None:
        client = LeonClient(base_url="http://localhost:1337")
        with patch("src.assistant.leon_client.request.urlopen", return_value=_FakeResponse('{"answer":"OK"}')):
            self.assertEqual(client.ask("salut"), "OK")

    def test_ask_supports_nested_data_format(self) -> None:
        client = LeonClient(base_url="http://localhost:1337")
        payload = '{"data":{"output":"Bonjour depuis data"}}'
        with patch("src.assistant.leon_client.request.urlopen", return_value=_FakeResponse(payload)):
            self.assertEqual(client.ask("salut"), "Bonjour depuis data")

    def test_ask_supports_answers_list_format(self) -> None:
        client = LeonClient(base_url="http://localhost:1337")
        payload = '{"answers":["premiere reponse","seconde"]}'
        with patch("src.assistant.leon_client.request.urlopen", return_value=_FakeResponse(payload)):
            self.assertEqual(client.ask("salut"), "premiere reponse")

    def test_ask_returns_none_on_unexpected_json_format(self) -> None:
        client = LeonClient(base_url="http://localhost:1337")
        with patch("src.assistant.leon_client.request.urlopen", return_value=_FakeResponse('{"foo":42}')):
            self.assertIsNone(client.ask("salut"))

    def test_ask_returns_none_when_service_unavailable(self) -> None:
        client = LeonClient(base_url="http://localhost:1337")
        with patch(
            "src.assistant.leon_client.request.urlopen",
            side_effect=error.URLError("service down"),
        ):
            self.assertIsNone(client.ask("salut"))

    def test_ask_retries_then_succeeds(self) -> None:
        client = LeonClient(base_url="http://localhost:1337", retry_attempts=2)
        with patch(
            "src.assistant.leon_client.request.urlopen",
            side_effect=[error.URLError("temporary"), _FakeResponse('{"answer":"OK apres retry"}')],
        ) as mocked:
            self.assertEqual(client.ask("salut"), "OK apres retry")
            self.assertEqual(mocked.call_count, 2)


if __name__ == "__main__":
    unittest.main()
