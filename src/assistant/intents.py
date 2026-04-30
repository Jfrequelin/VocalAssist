from __future__ import annotations

from datetime import datetime
from typing import Callable, TypedDict


ResponseFactory = Callable[[datetime], str]


class IntentConfig(TypedDict):
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


INTENT_REGISTRY: dict[str, IntentConfig] = {
    "time": {
        "keywords": ["heure", "time"],
        "response": _time_response,
    },
    "date": {
        "keywords": ["date", "jour"],
        "response": _date_response,
    },
    "weather": {
        "keywords": ["meteo"],
        "response": _weather_response,
    },
    "music": {
        "keywords": ["musique", "chanson", "play"],
        "response": _music_response,
    },
    "light": {
        "keywords": ["lumiere", "lampe"],
        "response": _light_response,
    },
    "reminder": {
        "keywords": ["rappel", "remember", "memo"],
        "response": _reminder_response,
    },
    "agenda": {
        "keywords": ["agenda", "calendrier", "planning"],
        "response": _agenda_response,
    },
    "exit": {
        "keywords": ["stop", "arrete", "quitte", "exit"],
        "response": _exit_response,
    },
}


def parse_intent(message: str) -> str:
    text = message.lower()

    for intent, data in INTENT_REGISTRY.items():
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
