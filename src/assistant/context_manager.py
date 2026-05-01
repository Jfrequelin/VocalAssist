"""
Context management module for multi-turn conversations.
Tracks conversation history, state, and entities.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, TypedDict, cast
import logging
import time

logger = logging.getLogger(__name__)


class ConversationData(TypedDict):
    """Typed structure for stored conversation data."""

    user_id: str
    created_at: datetime
    ended_at: Optional[datetime]
    memory: "ContextMemory"
    state: "StateTracker"
    active: bool


@dataclass
class ConversationContext:
    """Single turn in a conversation."""

    user_input: str
    assistant_response: str
    intent: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    slots: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))
    entities: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))
    metadata: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))


class ContextMemory:
    """Manages conversation memory with configurable size."""

    def __init__(self, max_turns: int = 20) -> None:
        """Initialize context memory.

        Args:
            max_turns: Maximum turns to keep in memory.
        """
        self.turns: list[ConversationContext] = []
        self.max_turns = max_turns

    def add_turn(self, context: ConversationContext) -> None:
        """Add turn to memory.

        Args:
            context: Conversation context to add.
        """
        self.turns.append(context)

        # Keep only recent turns
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_turns(self) -> list[ConversationContext]:
        """Get all turns in memory.

        Returns:
            List of conversation contexts.
        """
        return self.turns.copy()

    def get_recent_turns(self, count: int = 5) -> list[ConversationContext]:
        """Get recent turns.

        Args:
            count: Number of recent turns to return.

        Returns:
            List of recent contexts.
        """
        return self.turns[-count:] if len(self.turns) >= count else self.turns

    def search_by_intent(self, intent: str) -> list[ConversationContext]:
        """Search memory by intent.

        Args:
            intent: Intent to search for.

        Returns:
            List of contexts with matching intent.
        """
        return [t for t in self.turns if t.intent == intent]

    def search_by_entity(self, entity_key: str, entity_value: str) -> list[ConversationContext]:
        """Search memory by entity.

        Args:
            entity_key: Entity key to search.
            entity_value: Entity value to match.

        Returns:
            List of contexts with matching entity.
        """
        return [
            t for t in self.turns
            if entity_key in t.entities and t.entities[entity_key] == entity_value
        ]

    def get_summary(self) -> dict[str, Any]:
        """Get memory summary.

        Returns:
            Dictionary with memory statistics.
        """
        intents: dict[str, int] = {}
        for turn in self.turns:
            intents[turn.intent] = intents.get(turn.intent, 0) + 1

        return {
            "total_turns": len(self.turns),
            "intents": intents,
            "first_turn": self.turns[0].timestamp if self.turns else None,
            "last_turn": self.turns[-1].timestamp if self.turns else None,
        }

    def clear(self) -> None:
        """Clear all memory."""
        self.turns.clear()


class StateTracker:
    """Manages conversation state with TTL support."""

    def __init__(self) -> None:
        """Initialize state tracker."""
        self.state: dict[str, tuple[Any, Optional[float]]] = {}

    def set_state(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set state value.

        Args:
            key: State key.
            value: State value.
            ttl: Time to live in seconds (None = infinite).
        """
        expiry = time.time() + ttl if ttl else None
        self.state[key] = (value, expiry)

    def get_state(self, key: str) -> Any:
        """Get state value.

        Args:
            key: State key.

        Returns:
            State value or None if not found or expired.
        """
        if key not in self.state:
            return None

        value, expiry = self.state[key]

        # Check expiration
        if expiry and time.time() > expiry:
            del self.state[key]
            return None

        return value

    def has_state(self, key: str) -> bool:
        """Check if state exists and is not expired.

        Args:
            key: State key.

        Returns:
            True if state exists and is valid.
        """
        return self.get_state(key) is not None

    def delete_state(self, key: str) -> bool:
        """Delete state.

        Args:
            key: State key.

        Returns:
            True if deleted, False if not found.
        """
        if key in self.state:
            del self.state[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all state."""
        self.state.clear()

    def get_all_state(self) -> dict[str, Any]:
        """Get all non-expired state.

        Returns:
            Dictionary of all state.
        """
        result: dict[str, Any] = {}
        expired_keys: list[str] = []

        for key, (value, expiry) in self.state.items():
            if expiry and time.time() > expiry:
                expired_keys.append(key)
            else:
                result[key] = value

        # Clean up expired keys
        for key in expired_keys:
            del self.state[key]

        return result


class ConversationManager:
    """Manages multiple concurrent conversations."""

    def __init__(self) -> None:
        """Initialize conversation manager."""
        self.conversations: dict[str, ConversationData] = {}

    def start_conversation(self, user_id: str) -> str:
        """Start a new conversation.

        Args:
            user_id: User identifier.

        Returns:
            Conversation ID.
        """
        conv_id = str(uuid.uuid4())
        self.conversations[conv_id] = {
            "user_id": user_id,
            "created_at": datetime.now(),
            "ended_at": None,
            "memory": ContextMemory(),
            "state": StateTracker(),
            "active": True,
        }
        logger.info(f"Started conversation {conv_id} for user {user_id}")
        return conv_id

    def add_exchange(
        self,
        conv_id: str,
        user_input: str,
        assistant_response: str,
        intent: str,
        **kwargs: Any
    ) -> None:
        """Add user-assistant exchange to conversation.

        Args:
            conv_id: Conversation ID.
            user_input: User message.
            assistant_response: Assistant response.
            intent: Detected intent.
            **kwargs: Additional context data (slots, entities, etc).
        """
        if conv_id not in self.conversations:
            logger.warning(f"Conversation {conv_id} not found")
            return

        context = ConversationContext(
            user_input=user_input,
            assistant_response=assistant_response,
            intent=intent,
            **{k: v for k, v in kwargs.items() if k in ['confidence', 'slots', 'entities', 'metadata']}
        )

        self.conversations[conv_id]["memory"].add_turn(context)

    def get_conversation_history(self, conv_id: str) -> list[ConversationContext]:
        """Get conversation history.

        Args:
            conv_id: Conversation ID.

        Returns:
            List of conversation contexts.
        """
        if conv_id not in self.conversations:
            return []

        return self.conversations[conv_id]["memory"].get_turns()

    def get_recent_context(self, conv_id: str, count: int = 5) -> list[ConversationContext]:
        """Get recent conversation context.

        Args:
            conv_id: Conversation ID.
            count: Number of recent turns.

        Returns:
            List of recent contexts.
        """
        if conv_id not in self.conversations:
            return []

        return self.conversations[conv_id]["memory"].get_recent_turns(count)

    def get_last_intent(self, conv_id: str) -> Optional[str]:
        """Get last intent in conversation.

        Args:
            conv_id: Conversation ID.

        Returns:
            Last intent or None.
        """
        turns = self.get_conversation_history(conv_id)
        return turns[-1].intent if turns else None

    def search_conversation(
        self,
        conv_id: str,
        intent: Optional[str] = None,
        entity_key: Optional[str] = None,
        entity_value: Optional[str] = None,
    ) -> list[ConversationContext]:
        """Search conversation history.

        Args:
            conv_id: Conversation ID.
            intent: Filter by intent.
            entity_key: Filter by entity key.
            entity_value: Filter by entity value.

        Returns:
            Filtered conversation contexts.
        """
        if conv_id not in self.conversations:
            return []

        memory = self.conversations[conv_id]["memory"]

        if intent:
            return memory.search_by_intent(intent)
        elif entity_key and entity_value:
            return memory.search_by_entity(entity_key, entity_value)
        else:
            return memory.get_turns()

    def set_conversation_state(self, conv_id: str, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set conversation state.

        Args:
            conv_id: Conversation ID.
            key: State key.
            value: State value.
            ttl: Time to live in seconds.
        """
        if conv_id not in self.conversations:
            return

        self.conversations[conv_id]["state"].set_state(key, value, ttl)

    def get_conversation_state(self, conv_id: str, key: str) -> Any:
        """Get conversation state.

        Args:
            conv_id: Conversation ID.
            key: State key.

        Returns:
            State value or None.
        """
        if conv_id not in self.conversations:
            return None

        return self.conversations[conv_id]["state"].get_state(key)

    def end_conversation(self, conv_id: str) -> None:
        """End a conversation.

        Args:
            conv_id: Conversation ID.
        """
        if conv_id in self.conversations:
            self.conversations[conv_id]["ended_at"] = datetime.now()
            self.conversations[conv_id]["active"] = False
            logger.info(f"Ended conversation {conv_id}")

    def conversation_exists(self, conv_id: str) -> bool:
        """Check if conversation exists.

        Args:
            conv_id: Conversation ID.

        Returns:
            True if conversation exists.
        """
        return conv_id in self.conversations

    def get_active_conversations(self) -> list[str]:
        """Get list of active conversation IDs.

        Returns:
            List of active conversation IDs.
        """
        return [
            cid for cid, conv in self.conversations.items()
            if conv["active"]
        ]

    def cleanup_old_conversations(self, hours: int = 24) -> int:
        """Clean up old conversations.

        Args:
            hours: Age threshold in hours.

        Returns:
            Number of conversations cleaned.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        to_delete: list[str] = []

        for conv_id, conv in self.conversations.items():
            if conv["created_at"] < cutoff:
                to_delete.append(conv_id)

        for conv_id in to_delete:
            del self.conversations[conv_id]

        logger.info(f"Cleaned up {len(to_delete)} old conversations")
        return len(to_delete)

    def get_conversation_stats(self, conv_id: str) -> dict[str, Any]:
        """Get conversation statistics.

        Args:
            conv_id: Conversation ID.

        Returns:
            Dictionary with statistics.
        """
        if conv_id not in self.conversations:
            return {}

        conv = self.conversations[conv_id]
        return conv["memory"].get_summary()
