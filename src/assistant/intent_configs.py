"""
Predefined intent configurations for AssistantVocal.
Migrates existing intents to the centralized registry (intents_v2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.assistant.intents_v2 import IntentRegistry, SlotDefinition, SlotType


def _time_response(slots: dict[str, Any]) -> str:
    """Generate time response."""
    return f"Il est {datetime.now().strftime('%H:%M')}."


def _date_response(slots: dict[str, Any]) -> str:
    """Generate date response."""
    return f"Nous sommes le {datetime.now().strftime('%d/%m/%Y')}."


def _weather_response(slots: dict[str, Any]) -> str:
    """Generate weather response."""
    city = slots.get("city", "")
    if city:
        return f"Simulation meteo {city}: ciel degage, 21 degres."
    return "Simulation meteo: ciel degage, 21 degres."


def _light_response(slots: dict[str, Any]) -> str:
    """Generate light control response."""
    state = str(slots.get("state", "on"))
    room = str(slots.get("room", "salon"))
    if state == "off":
        return f"Simulation domotique: lumiere du {room} eteinte."
    return f"Simulation domotique: lumiere du {room} allumee."


def _music_response(slots: dict[str, Any]) -> str:
    """Generate music response."""
    action = str(slots.get("action", "play"))
    if action == "stop":
        return "Simulation musique: lecture arretee."
    
    details: list[str] = []
    if "genre" in slots:
        details.append(f"genre {slots['genre']}")
    if "volume" in slots:
        details.append(f"volume {slots['volume']}")
    suffix = f" ({', '.join(details)})" if details else ""
    return f"Simulation musique: lecture lancee{suffix}."


def _temperature_response(slots: dict[str, Any]) -> str:
    """Generate temperature response."""
    value = slots.get("value")
    if value:
        return f"Simulation climatisation: temperature reglee a {value} degres."
    return "Simulation climatisation: temperature ajustee."


def _reminder_response(slots: dict[str, Any]) -> str:
    """Generate reminder response."""
    return "Simulation rappel: c'est note pour demain matin."


def _agenda_response(slots: dict[str, Any]) -> str:
    """Generate agenda response."""
    return "Simulation agenda: vous avez 2 evenements aujourd'hui."


def _mute_response(slots: dict[str, Any]) -> str:
    """Generate mute response."""
    return "Simulation audio: mode muet active."


def _volume_response(slots: dict[str, Any]) -> str:
    """Generate volume response."""
    return "Simulation audio: volume ajuste."


def _restart_response(slots: dict[str, Any]) -> str:
    """Generate restart response."""
    return "Simulation systeme: redemarrage prepare."


def _stop_media_response(slots: dict[str, Any]) -> str:
    """Generate stop media response."""
    return "Simulation media: lecture arretee."


def _system_help_response(slots: dict[str, Any]) -> str:
    """Generate system help response."""
    return "Aide systeme: commandes critiques disponibles -> mute, volume, restart, stop media, aide."


def _exit_response(slots: dict[str, Any]) -> str:
    """Generate exit response."""
    return "A bientot. Fermeture de l'assistant."


def _timer_response(slots: dict[str, Any]) -> str:
    """Generate timer response."""
    duration = slots.get("duration", 5)
    unit = slots.get("unit", "minutes")
    return f"Minuteur programme pour {duration} {unit}."


def _notes_response(slots: dict[str, Any]) -> str:
    """Generate notes/todo response."""
    action = slots.get("action", "ajouter")
    if action == "lister":
        return "Simulation notes: vous avez 3 notes."
    return "Simulation notes: note sauvegardee."


def _search_response(slots: dict[str, Any]) -> str:
    """Generate search response."""
    query = slots.get("query", "")
    if query:
        return f"Simulation recherche: resultats pour '{query}'."
    return "Simulation recherche: pret a chercher."


def _settings_response(slots: dict[str, Any]) -> str:
    """Generate settings response."""
    setting = slots.get("setting", "")
    value = slots.get("value", "")
    if value:
        return f"Parametres: {setting} regle a {value}."
    return f"Parametres: {setting} modifie."


def create_default_registry() -> IntentRegistry:
    """Create and configure the default intent registry."""
    registry = IntentRegistry()

    # Exit (highest priority - must be checked first)
    registry.register(
        intent_id="exit",
        keywords=["stop", "arrete", "quitte", "exit", "ferme", "bye", "aurevoir"],
        priority=100,
        response_factory=_exit_response,
    )

    # Stop media (high priority)
    registry.register(
        intent_id="stop_media",
        keywords=["stop la musique", "arrete la musique", "pause musique", "arrete musique", "coupe la musique"],
        priority=95,
        response_factory=_stop_media_response,
    )

    # Mute
    registry.register(
        intent_id="mute",
        keywords=["mute", "coupe le son", "mode muet", "silence"],
        priority=90,
        response_factory=_mute_response,
    )

    # Volume
    registry.register(
        intent_id="volume",
        keywords=["volume", "son", "augmente", "baisse"],
        priority=85,
        response_factory=_volume_response,
    )

    # Restart
    registry.register(
        intent_id="restart",
        keywords=["redemarrage", "redémarre", "restart", "relance"],
        priority=80,
        response_factory=_restart_response,
    )

    # Light (with slots)
    registry.register(
        intent_id="light",
        keywords=["lumiere", "eclairage", "allume", "eteins", "lampe"],
        priority=75,
        slots={
            "room": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["salon", "chambre", "cuisine", "bureau"],
                required=False,
            ),
            "state": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["on", "off"],
                required=False,
            ),
        },
        response_factory=_light_response,
    )

    # Music (with slots)
    registry.register(
        intent_id="music",
        keywords=["musique", "chanson", "radio", "play", "lance", "joue"],
        priority=70,
        slots={
            "action": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["play", "stop", "pause"],
                required=False,
            ),
            "genre": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["rock", "jazz", "pop", "classique", "electro"],
                required=False,
            ),
            "volume": SlotDefinition(
                slot_type=SlotType.NUMERIC,
                min_value=0,
                max_value=100,
                required=False,
            ),
        },
        response_factory=_music_response,
    )

    # Weather (with slots)
    registry.register(
        intent_id="weather",
        keywords=["meteo", "météo", "temps", "climat", "pluie"],
        priority=65,
        slots={
            "city": SlotDefinition(
                slot_type=SlotType.STRING,
                required=False,
            ),
        },
        response_factory=_weather_response,
    )

    # Temperature (with slots)
    registry.register(
        intent_id="temperature",
        keywords=["temperature", "thermostat", "degres", "chaud", "froid"],
        priority=60,
        slots={
            "value": SlotDefinition(
                slot_type=SlotType.NUMERIC,
                min_value=10,
                max_value=30,
                required=False,
            ),
        },
        response_factory=_temperature_response,
    )

    # Time
    registry.register(
        intent_id="time",
        keywords=["heure", "quelle heure", "l'heure", "c'est"],
        priority=55,
        response_factory=_time_response,
    )

    # Date
    registry.register(
        intent_id="date",
        keywords=["date", "quel jour", "aujourd'hui", "demain"],
        priority=55,
        response_factory=_date_response,
    )

    # Reminder
    registry.register(
        intent_id="reminder",
        keywords=["rappel", "remember", "rappelle"],
        priority=48,
        response_factory=_reminder_response,
    )

    # Agenda / Calendar
    registry.register(
        intent_id="agenda",
        keywords=["agenda", "calendrier", "planning", "evenement", "événement"],
        priority=50,
        response_factory=_agenda_response,
    )

    # System help
    registry.register(
        intent_id="system_help",
        keywords=["aide", "aide systeme", "help", "?"],
        priority=45,
        response_factory=_system_help_response,
    )

    # NEW: Timer/Alarm (MACRO-002-T2)
    registry.register(
        intent_id="timer",
        keywords=["minuteur", "timer", "alarme", "minuterie", "alarmer", "demarre un minuteur"],
        priority=40,
        slots={
            "duration": SlotDefinition(
                slot_type=SlotType.NUMERIC,
                min_value=1,
                max_value=3600,
                required=False,
            ),
            "unit": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["secondes", "minutes", "heures"],
                required=False,
            ),
        },
        response_factory=_timer_response,
    )

    # NEW: Notes/TODO (MACRO-002-T2)
    registry.register(
        intent_id="notes",
        keywords=["note", "notes", "todo", "todos", "tache", "taches", "rappel", "ajoute une note", "liste mes notes"],
        priority=49,
        slots={
            "action": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["ajouter", "lister", "supprime", "delete"],
                required=False,
            ),
            "content": SlotDefinition(
                slot_type=SlotType.STRING,
                required=False,
            ),
        },
        response_factory=_notes_response,
    )

    # NEW: Search (MACRO-002-T2)
    registry.register(
        intent_id="search",
        keywords=["cherche", "recherche", "trouve", "search", "google"],
        priority=35,
        slots={
            "query": SlotDefinition(
                slot_type=SlotType.STRING,
                required=False,
            ),
        },
        response_factory=_search_response,
    )

    # NEW: Settings/Configuration (MACRO-002-T2)
    registry.register(
        intent_id="settings",
        keywords=["parametres", "reglages", "config", "configuration", "modifie la langue"],
        priority=35,
        slots={
            "setting": SlotDefinition(
                slot_type=SlotType.ENUM,
                enum_values=["langue", "volume", "luminosite", "heure", "mode"],
                required=False,
            ),
            "value": SlotDefinition(
                slot_type=SlotType.STRING,
                required=False,
            ),
        },
        response_factory=_settings_response,
    )

    return registry
