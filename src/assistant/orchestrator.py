from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from time import monotonic
from typing import Any

from src.assistant.intents import extract_slots, parse_intent, respond
from src.assistant.leon_client import LeonClient


LOGGER = logging.getLogger(__name__)


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    consecutive_failures: int = 0
    open_until: float = 0.0

    def allow_request(self) -> bool:
        return monotonic() >= self.open_until

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.open_until = 0.0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.open_until = monotonic() + self.cooldown_seconds


LEON_CIRCUIT_BREAKER = CircuitBreaker(
    failure_threshold=max(1, int(os.getenv("LEON_CB_FAILURE_THRESHOLD", "3"))),
    cooldown_seconds=max(1.0, float(os.getenv("LEON_CB_COOLDOWN_SECONDS", "30"))),
)


def reset_leon_circuit_breaker() -> None:
    LEON_CIRCUIT_BREAKER.record_success()


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

    if not LEON_CIRCUIT_BREAKER.allow_request():
        trace["route"] = "fallback-error"
        trace["reason"] = "circuit_open"
        LOGGER.warning("routing=fallback-error intent=unknown reason=circuit_open")
        return AssistantReply(
            intent=intent,
            answer="Service Leon temporairement suspendu apres echecs repetes.",
            source="fallback-error",
            routing_trace=trace,
        )

    leon = LeonClient.from_env()
    leon_answer = leon.ask(message)
    if leon_answer:
        LEON_CIRCUIT_BREAKER.record_success()
        trace["route"] = "leon"
        trace["reason"] = "unknown_intent"
        LOGGER.info("routing=leon intent=unknown")
        return AssistantReply(intent=intent, answer=leon_answer, source="leon", routing_trace=trace)

    LEON_CIRCUIT_BREAKER.record_failure()
    trace["route"] = "fallback-error"
    trace["reason"] = "leon_unavailable_or_unexpected_format"
    trace["consecutive_failures"] = LEON_CIRCUIT_BREAKER.consecutive_failures
    LOGGER.warning("routing=fallback-error intent=unknown reason=leon_unavailable_or_unexpected_format")
    return AssistantReply(
        intent=intent,
        answer="Je ne comprends pas encore cette demande en local et Leon est indisponible.",
        source="fallback-error",
        routing_trace=trace,
    )
