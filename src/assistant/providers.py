from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from urllib import error, parse, request


class ProviderUnavailableError(RuntimeError):
    pass


class AssistantProvider(Protocol):
    def execute(self, slots: Mapping[str, object]) -> str:
        ...


def _read_json_response(response: Any) -> Any:
    raw = response.read().decode("utf-8").strip()
    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _extract_message(body: Any) -> str | None:
    if isinstance(body, str):
        text = body.strip()
        return text or None

    if not isinstance(body, Mapping):
        return None

    body_map = cast(dict[str, Any], body)
    for key in ["message", "answer", "output", "response", "text"]:
        value = body_map.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    data = body_map.get("data")
    if isinstance(data, Mapping):
        data_map = cast(dict[str, Any], data)
        for key in ["message", "answer", "output", "response", "text"]:
            value = data_map.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _build_bearer_headers(token: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@dataclass
class HomeAssistantLightProvider:
    base_url: str
    token: str
    room_entities: dict[str, str]
    default_entity_id: str | None = None
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "HomeAssistantLightProvider" | None:
        base_url = os.getenv("HOME_ASSISTANT_URL")
        token = os.getenv("HOME_ASSISTANT_TOKEN")
        if not base_url or not token:
            return None

        room_entities: dict[str, str] = {}
        for room in ["salon", "chambre", "cuisine", "bureau"]:
            env_name = f"HOME_ASSISTANT_LIGHT_{room.upper()}"
            entity_id = os.getenv(env_name)
            if entity_id:
                room_entities[room] = entity_id.strip()

        default_entity_id = os.getenv("HOME_ASSISTANT_LIGHT_DEFAULT_ENTITY")
        return cls(
            base_url=base_url.rstrip("/"),
            token=token.strip(),
            room_entities=room_entities,
            default_entity_id=default_entity_id.strip() if default_entity_id else None,
            timeout_seconds=max(0.1, float(os.getenv("HOME_ASSISTANT_TIMEOUT_SECONDS", "5"))),
        )

    def execute(self, slots: Mapping[str, object]) -> str:
        state = str(slots.get("state", "on")).lower()
        room = str(slots.get("room", "salon")).lower()
        entity_id = self.room_entities.get(room, self.default_entity_id)
        if not entity_id:
            raise ProviderUnavailableError("missing_entity")

        service = "turn_off" if state == "off" else "turn_on"
        payload = json.dumps({"entity_id": entity_id}).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/services/light/{service}",
            data=payload,
            headers=_build_bearer_headers(self.token),
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds):
                pass
        except (error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise ProviderUnavailableError("home_assistant_unavailable") from exc

        verb = "eteinte" if state == "off" else "allumee"
        return f"Domotique Home Assistant: lumiere du {room} {verb}."


@dataclass
class WeatherProvider:
    url_template: str
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "WeatherProvider" | None:
        url_template = os.getenv("WEATHER_PROVIDER_URL_TEMPLATE")
        if not url_template:
            return None
        return cls(
            url_template=url_template,
            timeout_seconds=max(0.1, float(os.getenv("WEATHER_PROVIDER_TIMEOUT_SECONDS", "5"))),
        )

    def execute(self, slots: Mapping[str, object]) -> str:
        city = str(slots.get("city", "local")).strip().lower() or "local"
        url = self.url_template.format(city=parse.quote(city))
        req = request.Request(url, headers={"Accept": "application/json"}, method="GET")

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = _read_json_response(response)
        except (error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise ProviderUnavailableError("weather_unavailable") from exc

        if isinstance(body, Mapping):
            body_map = cast(dict[str, Any], body)
            current_condition = body_map.get("current_condition")
            if isinstance(current_condition, list) and current_condition:
                first_condition = current_condition[0]
                if isinstance(first_condition, Mapping):
                    condition_map = cast(dict[str, Any], first_condition)
                    temperature = condition_map.get("temp_C")
                    weather_desc = condition_map.get("weatherDesc")
                    description = None
                    if isinstance(weather_desc, list) and weather_desc:
                        first_desc = weather_desc[0]
                        if isinstance(first_desc, Mapping):
                            description = cast(dict[str, Any], first_desc).get("value")
                    if isinstance(temperature, str) and isinstance(description, str):
                        return f"Meteo {city}: {description}, {temperature} degres."

            message = _extract_message(body_map)
            if message is not None:
                return message

        message = _extract_message(body)
        if message is not None:
            return message

        raise ProviderUnavailableError("weather_invalid_payload")


@dataclass
class WebhookMusicProvider:
    url: str
    timeout_seconds: float = 5.0
    auth_token: str | None = None

    @classmethod
    def from_env(cls) -> "WebhookMusicProvider" | None:
        url = os.getenv("MUSIC_PROVIDER_URL")
        if not url:
            return None
        auth_token = os.getenv("MUSIC_PROVIDER_AUTH_TOKEN")
        return cls(
            url=url,
            timeout_seconds=max(0.1, float(os.getenv("MUSIC_PROVIDER_TIMEOUT_SECONDS", "5"))),
            auth_token=auth_token.strip() if auth_token else None,
        )

    def execute(self, slots: Mapping[str, object]) -> str:
        payload: dict[str, object] = {"action": str(slots.get("action", "play"))}
        if "genre" in slots:
            payload["genre"] = slots["genre"]
        if "volume" in slots:
            payload["volume"] = slots["volume"]

        req = request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=_build_bearer_headers(self.auth_token),
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = _read_json_response(response)
        except (error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise ProviderUnavailableError("music_unavailable") from exc

        message = _extract_message(body)
        if message is not None:
            return message

        action = str(payload["action"])
        if action == "stop":
            return "Lecture arretee via provider musique."

        details: list[str] = []
        genre = payload.get("genre")
        volume = payload.get("volume")
        if isinstance(genre, str):
            details.append(f"genre {genre}")
        if isinstance(volume, int):
            details.append(f"volume {volume}")
        suffix = f" ({', '.join(details)})" if details else ""
        return f"Lecture lancee via provider musique{suffix}."


@dataclass
class ProviderRegistry:
    providers: dict[str, AssistantProvider]

    @classmethod
    def from_env(cls) -> "ProviderRegistry":
        providers: dict[str, AssistantProvider] = {}

        light_provider = HomeAssistantLightProvider.from_env()
        if light_provider is not None:
            providers["light"] = light_provider

        weather_provider = WeatherProvider.from_env()
        if weather_provider is not None:
            providers["weather"] = weather_provider

        music_provider = WebhookMusicProvider.from_env()
        if music_provider is not None:
            providers["music"] = music_provider

        return cls(providers)

    def execute(self, intent: str, slots: Mapping[str, object], fallback_message: str) -> str:
        provider = self.providers.get(intent)
        if provider is None:
            return fallback_message

        try:
            return provider.execute(slots)
        except ProviderUnavailableError:
            return f"Service externe indisponible pour {intent}. {fallback_message}"
