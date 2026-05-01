from __future__ import annotations

import re
from dataclasses import dataclass

from src.assistant.intents import IntentSlots


KNOWN_ROOMS = ("salon", "chambre", "cuisine", "bureau")
KNOWN_DEVICES = ("chauffage", "climatisation", "thermostat")


@dataclass(frozen=True)
class ClarificationRequest:
    intent: str
    slot: str
    prompt: str


def _word_matches(text: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _extract_room_candidates(text: str) -> list[str]:
    return [room for room in KNOWN_ROOMS if _word_matches(text, room)]


def _extract_city_candidates(text: str) -> list[str]:
    candidates = [match.strip() for match in re.findall(r"\b(?:a|de|pour)\s+([a-z][a-z\-]+)", text)]
    unique: list[str] = []
    for city in candidates:
        if city not in unique:
            unique.append(city)
    return unique


def _extract_device_candidates(text: str) -> list[str]:
    return [device for device in KNOWN_DEVICES if _word_matches(text, device)]


def detect_clarification_need(intent: str, slots: IntentSlots, normalized_message: str) -> ClarificationRequest | None:
    if intent == "light":
        rooms = _extract_room_candidates(normalized_message)
        if len(rooms) > 1:
            joined = " ou ".join(rooms)
            return ClarificationRequest(
                intent=intent,
                slot="room",
                prompt=f"Pour quelle piece exactement ? J'ai compris: {joined}.",
            )
        if "room" not in slots:
            return ClarificationRequest(
                intent=intent,
                slot="room",
                prompt="Pour quelle piece souhaitez-vous controler la lumiere ?",
            )

    if intent == "weather":
        cities = _extract_city_candidates(normalized_message)
        if len(cities) > 1:
            joined = " ou ".join(cities)
            return ClarificationRequest(
                intent=intent,
                slot="city",
                prompt=f"Pour quelle ville exactement ? J'ai detecte: {joined}.",
            )
        if "city" not in slots:
            return ClarificationRequest(
                intent=intent,
                slot="city",
                prompt="Pour quelle ville voulez-vous la meteo ?",
            )

    if intent == "temperature":
        devices = _extract_device_candidates(normalized_message)
        if len(devices) > 1:
            joined = " ou ".join(devices)
            return ClarificationRequest(
                intent=intent,
                slot="device",
                prompt=f"Quel appareil souhaitez-vous regler ? J'ai detecte: {joined}.",
            )

    return None


def extract_slot_value_from_followup(slot: str, normalized_message: str) -> str | None:
    if slot == "room":
        candidates = _extract_room_candidates(normalized_message)
        if len(candidates) == 1:
            return candidates[0]
        return None

    if slot == "city":
        # Accept plain city answer ("paris") or preposition form ("a paris").
        direct = re.fullmatch(r"([a-z][a-z\-]+)", normalized_message)
        if direct:
            return direct.group(1)

        candidates = _extract_city_candidates(normalized_message)
        if len(candidates) == 1:
            return candidates[0]
        return None

    if slot == "device":
        candidates = _extract_device_candidates(normalized_message)
        if len(candidates) == 1:
            return candidates[0]
        return None

    return None
