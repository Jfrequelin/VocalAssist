from __future__ import annotations

import logging
import os
import unicodedata
from dataclasses import dataclass
from time import monotonic
from typing import Any
from uuid import uuid4

from src.assistant.clarification import detect_clarification_need, extract_slot_value_from_followup
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
    correlation_id: str
    routing_trace: dict[str, Any]


@dataclass
class PendingClarification:
    intent: str
    slot: str
    slots: dict[str, Any]


PENDING_CLARIFICATIONS: dict[str, PendingClarification] = {}


def reset_pending_clarifications() -> None:
    PENDING_CLARIFICATIONS.clear()


def _normalize_text(message: str) -> str:
    lowered = message.lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def handle_message(
    message: str,
    use_leon_fallback: bool = True,
    correlation_id: str | None = None,
    conversation_id: str | None = None,
) -> AssistantReply:
    cid = correlation_id or str(uuid4())
    conv_id = conversation_id or "default"
    normalized_message = _normalize_text(message)

    pending = PENDING_CLARIFICATIONS.get(conv_id)
    if pending is not None:
        merged_slots: dict[str, Any] = dict(pending.slots)
        merged_slots.update(extract_slots(message, pending.intent))

        extracted = extract_slot_value_from_followup(pending.slot, normalized_message)
        if extracted is not None:
            merged_slots[pending.slot] = extracted

        need = detect_clarification_need(pending.intent, merged_slots, normalized_message)
        if need is not None and pending.slot not in merged_slots:
            trace = {
                "correlation_id": cid,
                "conversation_id": conv_id,
                "message": message,
                "detected_intent": pending.intent,
                "route": "local-clarification",
                "slot": pending.slot,
                "reason": "clarification_still_needed",
                "slots": merged_slots,
            }
            return AssistantReply(
                intent=pending.intent,
                answer=need.prompt,
                source="local-clarification",
                correlation_id=cid,
                routing_trace=trace,
            )

        del PENDING_CLARIFICATIONS[conv_id]
        trace = {
            "correlation_id": cid,
            "conversation_id": conv_id,
            "message": message,
            "detected_intent": pending.intent,
            "route": "local",
            "reason": "clarification_resolved",
            "slots": merged_slots,
        }
        return AssistantReply(
            intent=pending.intent,
            answer=respond(pending.intent, merged_slots),
            source="local",
            correlation_id=cid,
            routing_trace=trace,
        )

    intent = parse_intent(message)
    trace: dict[str, Any] = {
        "correlation_id": cid,
        "conversation_id": conv_id,
        "message": message,
        "detected_intent": intent,
        "use_leon_fallback": use_leon_fallback,
    }

    if intent != "unknown":
        slots = extract_slots(message, intent)

        clarification = detect_clarification_need(intent, slots, normalized_message)
        if clarification is not None:
            PENDING_CLARIFICATIONS[conv_id] = PendingClarification(
                intent=intent,
                slot=clarification.slot,
                slots=dict(slots),
            )
            trace["route"] = "local-clarification"
            trace["slot"] = clarification.slot
            trace["reason"] = "slot_missing_or_ambiguous"
            trace["slots"] = slots
            LOGGER.info(
                "event=routing_decision cid=%s route=local-clarification intent=%s slot=%s",
                cid,
                intent,
                clarification.slot,
            )
            return AssistantReply(
                intent=intent,
                answer=clarification.prompt,
                source="local-clarification",
                correlation_id=cid,
                routing_trace=trace,
            )

        trace["route"] = "local"
        trace["slots"] = slots
        LOGGER.info("event=routing_decision cid=%s route=local intent=%s", cid, intent)
        return AssistantReply(
            intent=intent,
            answer=respond(intent, slots),
            source="local",
            correlation_id=cid,
            routing_trace=trace,
        )

    if not use_leon_fallback:
        trace["route"] = "local"
        trace["reason"] = "fallback_disabled"
        LOGGER.info(
            "event=routing_decision cid=%s route=local intent=unknown reason=fallback_disabled",
            cid,
        )
        return AssistantReply(
            intent=intent,
            answer=respond(intent),
            source="local",
            correlation_id=cid,
            routing_trace=trace,
        )

    if not LEON_CIRCUIT_BREAKER.allow_request():
        trace["route"] = "fallback-error"
        trace["reason"] = "circuit_open"
        LOGGER.warning("event=routing_decision cid=%s route=fallback-error intent=unknown reason=circuit_open", cid)
        return AssistantReply(
            intent=intent,
            answer="Service Leon temporairement suspendu apres echecs repetes.",
            source="fallback-error",
            correlation_id=cid,
            routing_trace=trace,
        )

    try:
        leon = LeonClient.from_env()
    except RuntimeError:
        LEON_CIRCUIT_BREAKER.record_failure()
        trace["route"] = "fallback-error"
        trace["reason"] = "leon_misconfigured"
        trace["consecutive_failures"] = LEON_CIRCUIT_BREAKER.consecutive_failures
        LOGGER.warning(
            "event=routing_decision cid=%s route=fallback-error intent=unknown "
            "reason=leon_misconfigured failures=%s",
            cid,
            LEON_CIRCUIT_BREAKER.consecutive_failures,
        )
        return AssistantReply(
            intent=intent,
            answer="Je ne comprends pas encore cette demande en local et Leon est indisponible.",
            source="fallback-error",
            correlation_id=cid,
            routing_trace=trace,
        )

    leon_answer = leon.ask(message)
    if leon_answer:
        LEON_CIRCUIT_BREAKER.record_success()
        trace["route"] = "leon"
        trace["reason"] = "unknown_intent"
        LOGGER.info("event=routing_decision cid=%s route=leon intent=unknown", cid)
        return AssistantReply(
            intent=intent,
            answer=leon_answer,
            source="leon",
            correlation_id=cid,
            routing_trace=trace,
        )

    LEON_CIRCUIT_BREAKER.record_failure()
    trace["route"] = "fallback-error"
    trace["reason"] = "leon_unavailable_or_unexpected_format"
    trace["consecutive_failures"] = LEON_CIRCUIT_BREAKER.consecutive_failures
    LOGGER.warning(
        "event=routing_decision cid=%s route=fallback-error intent=unknown "
        "reason=leon_unavailable_or_unexpected_format failures=%s",
        cid,
        LEON_CIRCUIT_BREAKER.consecutive_failures,
    )
    return AssistantReply(
        intent=intent,
        answer="Je ne comprends pas encore cette demande en local et Leon est indisponible.",
        source="fallback-error",
        correlation_id=cid,
        routing_trace=trace,
    )
