from __future__ import annotations

from dataclasses import dataclass

from src.assistant.intents import extract_slots, parse_intent, respond
from src.assistant.leon_client import LeonClient


@dataclass
class AssistantReply:
    intent: str
    answer: str
    source: str


def handle_message(message: str, use_leon_fallback: bool = True) -> AssistantReply:
    intent = parse_intent(message)

    if intent != "unknown":
        slots = extract_slots(message, intent)
        return AssistantReply(intent=intent, answer=respond(intent, slots), source="local")

    if not use_leon_fallback:
        return AssistantReply(intent=intent, answer=respond(intent), source="local")

    leon = LeonClient.from_env()
    leon_answer = leon.ask(message)
    if leon_answer:
        return AssistantReply(intent=intent, answer=leon_answer, source="leon")

    return AssistantReply(
        intent=intent,
        answer="Je ne comprends pas encore cette demande en local et Leon est indisponible.",
        source="fallback-error",
    )
