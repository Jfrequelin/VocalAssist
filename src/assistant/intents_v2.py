"""
MACRO-002-T1: Centralized intent registry structure.
Provides a unified way to define intents, slots, and validation rules.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class SlotType(Enum):
    """Types of slots that can be extracted from user input."""

    STRING = "string"
    ENUM = "enum"
    NUMERIC = "numeric"
    BOOLEAN = "boolean"


@dataclass
class SlotDefinition:
    """Configuration for a slot to be extracted from user input."""

    slot_type: SlotType
    required: bool = False
    enum_values: list[str] = field(default_factory=list)
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern for extraction


@dataclass
class IntentDefinition:
    """Complete definition of an intent."""

    intent_id: str
    keywords: list[str]
    priority: int = 50
    slots: dict[str, SlotDefinition] = field(default_factory=dict)
    response_template: Optional[str] = None
    response_factory: Optional[Callable[[dict[str, Any]], str]] = None


class IntentRegistry:
    """Centralized registry for all intents with consistent structure."""

    def __init__(self) -> None:
        self._intents: dict[str, IntentDefinition] = {}

    def register(
        self,
        intent_id: str,
        keywords: list[str],
        priority: int = 50,
        slots: Optional[dict[str, SlotDefinition]] = None,
        response_template: Optional[str] = None,
        response_factory: Optional[Callable[[dict[str, Any]], str]] = None,
    ) -> None:
        """Register a new intent definition."""
        if slots is None:
            slots = {}

        definition = IntentDefinition(
            intent_id=intent_id,
            keywords=keywords,
            priority=priority,
            slots=slots,
            response_template=response_template,
            response_factory=response_factory,
        )

        self._intents[intent_id] = definition

    def get(self, intent_id: str) -> dict[str, Any] | None:
        """Get intent definition by ID."""
        definition = self._intents.get(intent_id)
        if definition is None:
            return None

        return {
            "intent_id": definition.intent_id,
            "keywords": definition.keywords,
            "priority": definition.priority,
            "slots": definition.slots,
            "response_template": definition.response_template,
            "response_factory": definition.response_factory,
        }

    def get_ordered(self) -> list[tuple[str, dict[str, Any]]]:
        """Get all intents ordered by priority (descending)."""
        sorted_items = sorted(
            self._intents.items(),
            key=lambda item: item[1].priority,
            reverse=True,
        )

        return [
            (intent_id, self._to_dict(definition))
            for intent_id, definition in sorted_items
        ]

    def _to_dict(self, definition: IntentDefinition) -> dict[str, Any]:
        """Convert IntentDefinition to dict."""
        return {
            "intent_id": definition.intent_id,
            "keywords": definition.keywords,
            "priority": definition.priority,
            "slots": definition.slots,
            "response_template": definition.response_template,
            "response_factory": definition.response_factory,
        }

    @staticmethod
    def _normalize_text(message: str) -> str:
        """Normalize text for matching (lowercase, remove accents)."""
        lowered = message.lower()
        decomposed = unicodedata.normalize("NFKD", lowered)
        no_diacritics = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
        return no_diacritics

    def matches_keywords(self, text: str, keywords: list[str]) -> bool:
        """Check if text matches any of the keywords."""
        normalized = self._normalize_text(text)

        for keyword in keywords:
            normalized_keyword = self._normalize_text(keyword)

            if " " in normalized_keyword:
                # Multi-word: substring match
                if normalized_keyword in normalized:
                    return True
            else:
                # Single word: word boundary match
                pattern = rf"\b{re.escape(normalized_keyword)}\b"
                if re.search(pattern, normalized):
                    return True

        return False

    def find_intent(self, text: str) -> str | None:
        """Find matching intent for given text."""
        ordered = self.get_ordered()

        for intent_id, data in ordered:
            keywords = data["keywords"]
            if keywords and self.matches_keywords(text, keywords):
                return intent_id

        return None
