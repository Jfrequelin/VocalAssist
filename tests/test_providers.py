from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src.assistant.intents import respond
from src.assistant.providers import (
    HomeAssistantLightProvider,
    ProviderRegistry,
    ProviderUnavailableError,
    WeatherProvider,
    WebhookMusicProvider,
)


class _FakeHttpResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class _StaticProvider:
    def execute(self, slots: dict[str, object]) -> str:
        del slots
        return "Provider externe OK"


class _FailingProvider:
    def execute(self, slots: dict[str, object]) -> str:
        del slots
        raise ProviderUnavailableError("unavailable")


class TestProviderRegistry(unittest.TestCase):
    def test_respond_uses_registered_provider(self) -> None:
        registry = ProviderRegistry({"light": _StaticProvider()})

        answer = respond("light", {"state": "on", "room": "salon"}, provider_registry=registry)

        self.assertEqual(answer, "Provider externe OK")

    def test_respond_uses_homogeneous_fallback_message_when_provider_fails(self) -> None:
        registry = ProviderRegistry({"light": _FailingProvider()})

        answer = respond("light", {"state": "on", "room": "salon"}, provider_registry=registry)

        self.assertIn("Service externe indisponible", answer)
        self.assertIn("lumiere du salon allumee", answer)


class TestHomeAssistantLightProvider(unittest.TestCase):
    @patch("src.assistant.providers.request.urlopen")
    def test_turn_on_light_for_room_entity(self, urlopen: object) -> None:
        captured: dict[str, object] = {}

        def _fake_urlopen(req: object, timeout: float) -> _FakeHttpResponse:
            captured["request"] = req
            captured["timeout"] = timeout
            return _FakeHttpResponse("[]")

        urlopen.side_effect = _fake_urlopen
        provider = HomeAssistantLightProvider(
            base_url="http://ha.local",
            token="secret-token",
            room_entities={"salon": "light.salon"},
            default_entity_id="light.default",
            timeout_seconds=4.0,
        )

        answer = provider.execute({"state": "on", "room": "salon"})

        self.assertIn("Home Assistant", answer)
        req = captured["request"]
        self.assertEqual(req.full_url, "http://ha.local/api/services/light/turn_on")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.headers.get("Authorization"), "Bearer secret-token")
        self.assertEqual(json.loads(req.data.decode("utf-8")), {"entity_id": "light.salon"})
        self.assertEqual(captured["timeout"], 4.0)


class TestWeatherProvider(unittest.TestCase):
    @patch("src.assistant.providers.request.urlopen")
    def test_weather_response_is_dynamic(self, urlopen: object) -> None:
        payload = json.dumps(
            {
                "current_condition": [
                    {
                        "temp_C": "18",
                        "weatherDesc": [{"value": "Ensoleille"}],
                    }
                ]
            }
        )
        urlopen.return_value = _FakeHttpResponse(payload)
        provider = WeatherProvider(
            url_template="https://weather.example/{city}",
            timeout_seconds=2.5,
        )

        answer = provider.execute({"city": "paris"})

        self.assertIn("paris", answer.lower())
        self.assertIn("18", answer)
        self.assertIn("Ensoleille", answer)


class TestWebhookMusicProvider(unittest.TestCase):
    @patch("src.assistant.providers.request.urlopen")
    def test_music_provider_posts_action_payload(self, urlopen: object) -> None:
        captured: dict[str, object] = {}

        def _fake_urlopen(req: object, timeout: float) -> _FakeHttpResponse:
            captured["request"] = req
            captured["timeout"] = timeout
            return _FakeHttpResponse('{"message": "Lecture rock lancee"}')

        urlopen.side_effect = _fake_urlopen
        provider = WebhookMusicProvider(
            url="https://music.example/play",
            timeout_seconds=3.0,
            auth_token="music-token",
        )

        answer = provider.execute({"action": "play", "genre": "rock", "volume": 30})

        self.assertEqual(answer, "Lecture rock lancee")
        req = captured["request"]
        self.assertEqual(req.full_url, "https://music.example/play")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.headers.get("Authorization"), "Bearer music-token")
        self.assertEqual(
            json.loads(req.data.decode("utf-8")),
            {"action": "play", "genre": "rock", "volume": 30},
        )
        self.assertEqual(captured["timeout"], 3.0)


if __name__ == "__main__":
    unittest.main()