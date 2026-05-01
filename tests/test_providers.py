from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src.assistant.intents import respond
from src.assistant.providers import (
    HomeAssistantClimateProvider,
    HomeAssistantLightProvider,
    HomeAssistantSceneProvider,
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

    @patch("src.assistant.providers.request.urlopen")
    def test_turn_on_10_consecutive_no_error(self, urlopen: object) -> None:
        urlopen.return_value = _FakeHttpResponse("[]")
        provider = HomeAssistantLightProvider(
            base_url="http://ha.local",
            token="tok",
            room_entities={"salon": "light.salon"},
        )
        for _ in range(10):
            answer = provider.execute({"state": "on", "room": "salon"})
            self.assertIn("allumee", answer)

    @patch("src.assistant.providers.request.urlopen")
    def test_turn_off_10_consecutive_no_error(self, urlopen: object) -> None:
        urlopen.return_value = _FakeHttpResponse("[]")
        provider = HomeAssistantLightProvider(
            base_url="http://ha.local",
            token="tok",
            room_entities={"salon": "light.salon"},
        )
        for _ in range(10):
            answer = provider.execute({"state": "off", "room": "salon"})
            self.assertIn("eteinte", answer)

    @patch("src.assistant.providers.request.urlopen")
    def test_idempotent_repeated_same_command(self, urlopen: object) -> None:
        """Rejouer la même commande doit toujours retourner le même résultat."""
        urlopen.return_value = _FakeHttpResponse("[]")
        provider = HomeAssistantLightProvider(
            base_url="http://ha.local",
            token="tok",
            room_entities={"chambre": "light.chambre"},
        )
        results = {provider.execute({"state": "on", "room": "chambre"}) for _ in range(5)}
        self.assertEqual(len(results), 1, "La même commande doit retourner un résultat identique")

    def test_missing_entity_raises_provider_error(self) -> None:
        provider = HomeAssistantLightProvider(
            base_url="http://ha.local",
            token="tok",
            room_entities={},
            default_entity_id=None,
        )
        with self.assertRaises(ProviderUnavailableError):
            provider.execute({"state": "on", "room": "salon"})

    @patch("src.assistant.providers.request.urlopen", side_effect=OSError("connexion refusee"))
    def test_network_error_raises_provider_unavailable(self, _urlopen: object) -> None:
        provider = HomeAssistantLightProvider(
            base_url="http://ha.local",
            token="tok",
            room_entities={"salon": "light.salon"},
        )
        with self.assertRaises(ProviderUnavailableError):
            provider.execute({"state": "on", "room": "salon"})


class TestHomeAssistantSceneProvider(unittest.TestCase):
    def _make_provider(self) -> HomeAssistantSceneProvider:
        return HomeAssistantSceneProvider(
            base_url="http://ha.local",
            token="tok",
            scene_entities={"soiree": "scene.soiree", "nuit": "scene.nuit", "film": "scene.film"},
            timeout_seconds=3.0,
        )

    @patch("src.assistant.providers.request.urlopen")
    def test_activate_scene_sends_correct_request(self, urlopen: object) -> None:
        captured: dict[str, object] = {}

        def _fake(req: object, timeout: float) -> _FakeHttpResponse:
            captured["req"] = req
            return _FakeHttpResponse("[]")

        urlopen.side_effect = _fake
        answer = self._make_provider().execute({"scene": "soiree"})

        self.assertIn("soiree", answer)
        self.assertIn("Home Assistant", answer)
        req = captured["req"]
        self.assertEqual(req.full_url, "http://ha.local/api/services/scene/turn_on")
        self.assertEqual(json.loads(req.data.decode("utf-8")), {"entity_id": "scene.soiree"})

    @patch("src.assistant.providers.request.urlopen")
    def test_activate_scene_10_consecutive(self, urlopen: object) -> None:
        urlopen.return_value = _FakeHttpResponse("[]")
        provider = self._make_provider()
        for _ in range(10):
            answer = provider.execute({"scene": "nuit"})
            self.assertIn("nuit", answer)

    @patch("src.assistant.providers.request.urlopen")
    def test_idempotent_scene_activation(self, urlopen: object) -> None:
        urlopen.return_value = _FakeHttpResponse("[]")
        results = {self._make_provider().execute({"scene": "film"}) for _ in range(5)}
        self.assertEqual(len(results), 1)

    def test_unknown_scene_raises_error(self) -> None:
        with self.assertRaises(ProviderUnavailableError):
            self._make_provider().execute({"scene": "inconnu"})

    @patch("src.assistant.providers.request.urlopen", side_effect=OSError("timeout"))
    def test_network_error_raises_unavailable(self, _urlopen: object) -> None:
        with self.assertRaises(ProviderUnavailableError):
            self._make_provider().execute({"scene": "soiree"})


class TestHomeAssistantClimateProvider(unittest.TestCase):
    def _make_provider(self) -> HomeAssistantClimateProvider:
        return HomeAssistantClimateProvider(
            base_url="http://ha.local",
            token="tok",
            climate_entity_id="climate.salon",
            min_temp=10.0,
            max_temp=30.0,
            timeout_seconds=3.0,
        )

    @patch("src.assistant.providers.request.urlopen")
    def test_set_temperature_sends_correct_request(self, urlopen: object) -> None:
        captured: dict[str, object] = {}

        def _fake(req: object, timeout: float) -> _FakeHttpResponse:
            captured["req"] = req
            return _FakeHttpResponse("[]")

        urlopen.side_effect = _fake
        answer = self._make_provider().execute({"value": "21"})

        self.assertIn("21", answer)
        self.assertIn("Home Assistant", answer)
        req = captured["req"]
        self.assertEqual(req.full_url, "http://ha.local/api/services/climate/set_temperature")
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["entity_id"], "climate.salon")
        self.assertEqual(body["temperature"], 21.0)

    @patch("src.assistant.providers.request.urlopen")
    def test_set_temperature_10_consecutive(self, urlopen: object) -> None:
        urlopen.return_value = _FakeHttpResponse("[]")
        provider = self._make_provider()
        for temp in range(18, 28):
            answer = provider.execute({"value": str(temp)})
            self.assertIn(str(temp), answer)

    @patch("src.assistant.providers.request.urlopen")
    def test_idempotent_same_temperature(self, urlopen: object) -> None:
        urlopen.return_value = _FakeHttpResponse("[]")
        results = {self._make_provider().execute({"value": "22"}) for _ in range(5)}
        self.assertEqual(len(results), 1)

    def test_temperature_out_of_range_raises_error(self) -> None:
        provider = self._make_provider()
        with self.assertRaises(ProviderUnavailableError):
            provider.execute({"value": "5"})
        with self.assertRaises(ProviderUnavailableError):
            provider.execute({"value": "45"})

    def test_invalid_temperature_raises_error(self) -> None:
        with self.assertRaises(ProviderUnavailableError):
            self._make_provider().execute({"value": "chaud"})

    @patch("src.assistant.providers.request.urlopen", side_effect=OSError("connexion"))
    def test_network_error_raises_unavailable(self, _urlopen: object) -> None:
        with self.assertRaises(ProviderUnavailableError):
            self._make_provider().execute({"value": "20"})


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
