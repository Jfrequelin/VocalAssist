from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Callable, TypedDict

from src.assistant.providers import ProviderRegistry


ResponseFactory = Callable[[datetime], str]


class IntentConfig(TypedDict):
    priority: int
    keywords: list[str]
    response: ResponseFactory


SlotValue = str | int
IntentSlots = dict[str, SlotValue]


def _time_response(now: datetime) -> str:
    return f"Il est {now.strftime('%H:%M')}."


def _date_response(now: datetime) -> str:
    return f"Nous sommes le {now.strftime('%d/%m/%Y')}."


def _weather_response(_now: datetime) -> str:
    return "Simulation meteo: ciel degage, 21 degres."


def _music_response(_now: datetime) -> str:
    return "Simulation musique: lecture de votre playlist focus."


def _light_response(_now: datetime) -> str:
    return "Simulation domotique: lumiere du salon allumee."


def _reminder_response(_now: datetime) -> str:
    return "Simulation rappel: c'est note pour demain matin."


def _agenda_response(_now: datetime) -> str:
    return "Simulation agenda: vous avez 2 evenements aujourd'hui."


def _exit_response(_now: datetime) -> str:
    return "A bientot. Fermeture de l'assistant."


def _mute_response(_now: datetime) -> str:
    return "Simulation audio: mode muet active."


def _volume_response(_now: datetime) -> str:
    return "Simulation audio: volume ajuste."


def _restart_response(_now: datetime) -> str:
    return "Simulation systeme: redemarrage prepare."


def _stop_media_response(_now: datetime) -> str:
    return "Simulation media: lecture arretee."


def _system_help_response(_now: datetime) -> str:
    return (
        "Aide systeme: commandes critiques disponibles -> mute, volume, restart, stop media, aide."
    )


def _temperature_response(_now: datetime) -> str:
    return "Simulation climatisation: temperature ajustee."


INTENT_REGISTRY: dict[str, IntentConfig] = {
    "stop_media": {
        "priority": 100,
        "keywords": [
            "stop la musique",
            "arrete la musique",
            "arrete musique",
            "pause musique",
            "stop media",
            "coupe la musique",
        ],
        "response": _stop_media_response,
    },
    "mute": {
        "priority": 95,
        "keywords": ["mute", "coupe le son", "mode muet", "silence"],
        "response": _mute_response,
    },
    "volume": {
        "priority": 90,
        "keywords": ["volume", "augmente le son", "baisse le son"],
        "response": _volume_response,
    },
    "restart": {
        "priority": 85,
        "keywords": ["restart", "redemarre", "redemarrer", "redemarrage"],
        "response": _restart_response,
    },
    "system_help": {
        "priority": 80,
        "keywords": ["aide systeme", "help system", "commande systeme", "help"],
        "response": _system_help_response,
    },
    "time": {
        "priority": 50,
        "keywords": ["heure", "time"],
        "response": _time_response,
    },
    "date": {
        "priority": 50,
        "keywords": ["date", "jour"],
        "response": _date_response,
    },
    "weather": {
        "priority": 50,
        "keywords": ["meteo"],
        "response": _weather_response,
    },
    "temperature": {
        "priority": 50,
        "keywords": ["temperature", "chauffage", "thermostat"],
        "response": _temperature_response,
    },
    "music": {
        "priority": 50,
        "keywords": ["musique", "chanson", "play"],
        "response": _music_response,
    },
    "light": {
        "priority": 50,
        "keywords": ["lumiere", "lampe"],
        "response": _light_response,
    },
    "reminder": {
        "priority": 50,
        "keywords": ["rappel", "remember", "memo"],
        "response": _reminder_response,
    },
    "agenda": {
        "priority": 50,
        "keywords": ["agenda", "calendrier", "planning"],
        "response": _agenda_response,
    },
    "exit": {
        "priority": 10,
        "keywords": ["stop", "arrete", "quitte", "exit"],
        "response": _exit_response,
    },
}


def _normalize_text(message: str) -> str:
    lowered = message.lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    no_diacritics = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return no_diacritics


def _keyword_matches(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text

    pattern = rf"\b{re.escape(keyword)}\b"
    return re.search(pattern, text) is not None


def parse_intent(message: str) -> str:
    text = _normalize_text(message)

    ordered_registry = sorted(
        INTENT_REGISTRY.items(),
        key=lambda item: item[1]["priority"],
        reverse=True,
    )

    for intent, data in ordered_registry:
        keywords = data["keywords"]
        if any(_keyword_matches(text, keyword) for keyword in keywords):
            return intent

    return "unknown"


def extract_slots(message: str, intent: str) -> IntentSlots:
    text = _normalize_text(message)
    slots: IntentSlots = {}

    if intent == "weather":
        city_match = re.search(r"\b(?:a|de|pour)\s+([a-z][a-z\- ]+)$", text)
        if city_match:
            slots["city"] = city_match.group(1).strip()

    if intent == "light":
        room_match = re.search(r"\b(salon|chambre|cuisine|bureau)\b", text)
        if room_match:
            slots["room"] = room_match.group(1)

        if any(keyword in text for keyword in ["allume", "active", "on"]):
            slots["state"] = "on"
        elif any(keyword in text for keyword in ["eteins", "coupe", "off"]):
            slots["state"] = "off"

    if intent == "music":
        if any(keyword in text for keyword in ["stop", "arrete", "pause"]):
            slots["action"] = "stop"
        elif any(keyword in text for keyword in ["play", "lance", "demarre"]):
            slots["action"] = "play"

        volume_match = re.search(r"(?:volume|son)\s*(\d{1,3})", text)
        if volume_match:
            slots["volume"] = int(volume_match.group(1))

        genre_match = re.search(r"\b(rock|jazz|pop|classique|electro)\b", text)
        if genre_match:
            slots["genre"] = genre_match.group(1)

    if intent == "temperature":
        temp_match = re.search(r"(-?\d{1,2})\s*(?:°|degres?|c)?", text)
        if temp_match:
            slots["value"] = int(temp_match.group(1))

    return slots


def validate_slots(intent: str, slots: IntentSlots) -> str | None:
    if intent == "light" and "state" not in slots:
        return "Precisez l'action lumiere: allumer ou eteindre."

    if intent == "music" and "volume" in slots:
        volume = slots["volume"]
        if isinstance(volume, int) and not 0 <= volume <= 100:
            return "Le volume doit etre compris entre 0 et 100."

    if intent == "temperature":
        if "value" not in slots:
            return "Precisez la temperature cible en degres."
        value = slots["value"]
        if isinstance(value, int) and not 10 <= value <= 30:
            return "La temperature doit etre comprise entre 10 et 30 degres."

    return None


def _local_response(intent: str, normalized_slots: IntentSlots, now: datetime) -> str:
    if intent == "weather":
        city = normalized_slots.get("city")
        if isinstance(city, str) and city:
            return f"Simulation meteo {city}: ciel degage, 21 degres."
        return "Simulation meteo: ciel degage, 21 degres."

    if intent == "light":
        state = normalized_slots.get("state", "on")
        room = str(normalized_slots.get("room", "salon"))
        if state == "off":
            return f"Simulation domotique: lumiere du {room} eteinte."
        return f"Simulation domotique: lumiere du {room} allumee."

    if intent == "music":
        action = str(normalized_slots.get("action", "play"))
        if action == "stop":
            return "Simulation musique: lecture arretee."

        genre = normalized_slots.get("genre")
        volume = normalized_slots.get("volume")
        details: list[str] = []
        if isinstance(genre, str):
            details.append(f"genre {genre}")
        if isinstance(volume, int):
            details.append(f"volume {volume}")
        suffix = f" ({', '.join(details)})" if details else ""
        return f"Simulation musique: lecture lancee{suffix}."

    if intent == "temperature":
        target = normalized_slots.get("value")
        if isinstance(target, int):
            return f"Simulation climatisation: temperature reglee a {target} degres."

    data = INTENT_REGISTRY.get(intent)
    if data is not None:
        response_factory = data["response"]
        return response_factory(now)

    return "Je n'ai pas compris la demande."


def _respond(
    intent: str,
    slots: IntentSlots | None = None,
    provider_registry: ProviderRegistry | None = None,
) -> str:
    now = datetime.now()
    normalized_slots = slots or {}

    validation_error = validate_slots(intent, normalized_slots)
    if validation_error:
        return validation_error

    fallback_response = _local_response(intent, normalized_slots, now)
    active_registry = provider_registry or ProviderRegistry.from_env()
    if intent in {"weather", "light", "music"}:
        return active_registry.execute(intent, normalized_slots, fallback_response)

    return fallback_response


def respond(
    intent: str,
    slots: IntentSlots | None = None,
    provider_registry: ProviderRegistry | None = None,
) -> str:
    return _respond(intent, slots, provider_registry)
