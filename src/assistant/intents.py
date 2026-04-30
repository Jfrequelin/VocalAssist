from __future__ import annotations

from datetime import datetime
from typing import Callable, TypedDict


ResponseFactory = Callable[[datetime], str]


class IntentConfig(TypedDict):
    priority: int
    keywords: list[str]
    response: ResponseFactory


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


def parse_intent(message: str) -> str:
    text = message.lower()

    ordered_registry = sorted(
        INTENT_REGISTRY.items(),
        key=lambda item: item[1]["priority"],
        reverse=True,
    )

    for intent, data in ordered_registry:
        keywords = data["keywords"]
        if any(keyword in text for keyword in keywords):
            return intent

    return "unknown"


def respond(intent: str) -> str:
    now = datetime.now()

    data = INTENT_REGISTRY.get(intent)
    if data is not None:
        response_factory = data["response"]
        return response_factory(now)

    return "Je n'ai pas compris la demande."
