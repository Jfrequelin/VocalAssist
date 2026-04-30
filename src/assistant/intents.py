from __future__ import annotations

from datetime import datetime


def parse_intent(message: str) -> str:
    text = message.lower()

    if any(k in text for k in ["heure", "time"]):
        return "time"
    if any(k in text for k in ["date", "jour"]):
        return "date"
    if "meteo" in text:
        return "weather"
    if any(k in text for k in ["musique", "chanson", "play"]):
        return "music"
    if any(k in text for k in ["lumiere", "lampe"]):
        return "light"
    if any(k in text for k in ["rappel", "remember", "memo"]):
        return "reminder"
    if any(k in text for k in ["agenda", "calendrier", "planning"]):
        return "agenda"
    if any(k in text for k in ["stop", "arrete", "quitte", "exit"]):
        return "exit"

    return "unknown"


def respond(intent: str) -> str:
    now = datetime.now()

    if intent == "time":
        return f"Il est {now.strftime('%H:%M')}."
    if intent == "date":
        return f"Nous sommes le {now.strftime('%d/%m/%Y')}."
    if intent == "weather":
        return "Simulation meteo: ciel degage, 21 degres."
    if intent == "music":
        return "Simulation musique: lecture de votre playlist focus."
    if intent == "light":
        return "Simulation domotique: lumiere du salon allumee."
    if intent == "reminder":
        return "Simulation rappel: c'est note pour demain matin."
    if intent == "agenda":
        return "Simulation agenda: vous avez 2 evenements aujourd'hui."
    if intent == "exit":
        return "A bientot. Fermeture de l'assistant."

    return "Je n'ai pas compris la demande."
