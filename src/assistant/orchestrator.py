from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.assistant.intents import extract_slots, parse_intent, respond
from src.assistant.leon_client import LeonClient


LOGGER = logging.getLogger(__name__)


@dataclass
class AssistantReply:
    intent: str
    answer: str
    source: str
    routing_trace: dict[str, Any]


def handle_message(message: str, use_leon_fallback: bool = True) -> AssistantReply:
    intent = parse_intent(message)
    trace: dict[str, Any] = {
        "message": message,
        "detected_intent": intent,
        "use_leon_fallback": use_leon_fallback,
    }

    if intent != "unknown":
        slots = extract_slots(message, intent)
        trace["route"] = "local"
        trace["slots"] = slots
        LOGGER.info("routing=local intent=%s", intent)
        return AssistantReply(intent=intent, answer=respond(intent, slots), source="local", routing_trace=trace)

    if not use_leon_fallback:
        trace["route"] = "local"
        trace["reason"] = "fallback_disabled"
        LOGGER.info("routing=local intent=unknown reason=fallback_disabled")
        return AssistantReply(intent=intent, answer=respond(intent), source="local", routing_trace=trace)

    leon = LeonClient.from_env()
    leon_answer = leon.ask(message)
    if leon_answer:
        trace["route"] = "leon"
        trace["reason"] = "unknown_intent"
        LOGGER.info("routing=leon intent=unknown")
        return AssistantReply(intent=intent, answer=leon_answer, source="leon", routing_trace=trace)

    trace["route"] = "fallback-error"
    trace["reason"] = "leon_unavailable_or_unexpected_format"
    LOGGER.warning("routing=fallback-error intent=unknown reason=leon_unavailable_or_unexpected_format")
    return AssistantReply(
        intent=intent,
        answer="Je ne comprends pas encore cette demande en local et Leon est indisponible.",
        source="fallback-error",
        routing_trace=trace,
    )
