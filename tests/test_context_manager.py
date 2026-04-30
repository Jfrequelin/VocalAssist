"""
Tests for MACRO-004-T2: Context management for multi-turn conversations
Tests conversation memory, context tracking, and state management.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from src.assistant.context_manager import (
    ConversationContext,
    ContextMemory,
    StateTracker,
    ConversationManager,
)


class TestConversationContext(unittest.TestCase):
    """Test conversation context tracking."""

    def test_create_conversation_context(self) -> None:
        """Test creating a conversation context."""
        context = ConversationContext(
            user_input="What was the weather yesterday?",
            assistant_response="It was sunny",
            intent="weather"
        )
        
        self.assertEqual(context.user_input, "What was the weather yesterday?")
        self.assertEqual(context.assistant_response, "It was sunny")
        self.assertEqual(context.intent, "weather")
        self.assertIsNotNone(context.timestamp)

    def test_context_with_slots(self) -> None:
        """Test context with extracted slots."""
        context = ConversationContext(
            user_input="Remind me tomorrow at 9am",
            assistant_response="Reminder set for tomorrow at 9am",
            intent="reminder",
            slots={"time": "tomorrow at 9am", "action": "remind"}
        )
        
        self.assertIn("time", context.slots)
        self.assertEqual(context.slots["action"], "remind")

    def test_context_with_entities(self) -> None:
        """Test context with named entities."""
        context = ConversationContext(
            user_input="Call John Smith at the office",
            assistant_response="Calling John Smith",
            intent="call",
            entities={"person": "John Smith", "location": "office"}
        )
        
        self.assertEqual(context.entities["person"], "John Smith")

    def test_context_confidence(self) -> None:
        """Test context with confidence scores."""
        context = ConversationContext(
            user_input="Maybe set a timer?",
            assistant_response="I'm not sure about that",
            intent="timer",
            confidence=0.4
        )
        
        self.assertEqual(context.confidence, 0.4)


class TestContextMemory(unittest.TestCase):
    """Test conversation memory."""

    def setUp(self) -> None:
        self.memory = ContextMemory(max_turns=10)

    def test_add_turn_to_memory(self) -> None:
        """Test adding conversation turn to memory."""
        context = ConversationContext(
            user_input="Hello",
            assistant_response="Hi there!",
            intent="greeting"
        )
        
        self.memory.add_turn(context)
        
        self.assertEqual(len(self.memory.get_turns()), 1)

    def test_memory_preserves_order(self) -> None:
        """Test that memory preserves turn order."""
        turns = [
            ConversationContext("First", "Response 1", "test"),
            ConversationContext("Second", "Response 2", "test"),
            ConversationContext("Third", "Response 3", "test"),
        ]
        
        for turn in turns:
            self.memory.add_turn(turn)
        
        retrieved = self.memory.get_turns()
        self.assertEqual(len(retrieved), 3)
        self.assertEqual(retrieved[0].user_input, "First")
        self.assertEqual(retrieved[2].user_input, "Third")

    def test_memory_max_size(self) -> None:
        """Test that memory respects max turns."""
        for i in range(15):
            context = ConversationContext(
                user_input=f"Turn {i}",
                assistant_response=f"Response {i}",
                intent="test"
            )
            self.memory.add_turn(context)
        
        # Should only keep last 10
        self.assertEqual(len(self.memory.get_turns()), 10)

    def test_get_recent_context(self) -> None:
        """Test getting recent conversation context."""
        for i in range(5):
            context = ConversationContext(
                user_input=f"Query {i}",
                assistant_response=f"Answer {i}",
                intent="test"
            )
            self.memory.add_turn(context)
        
        recent = self.memory.get_recent_turns(2)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0].user_input, "Query 3")

    def test_search_memory_by_intent(self) -> None:
        """Test searching memory by intent."""
        self.memory.add_turn(ConversationContext("Turn 1", "Response", "weather"))
        self.memory.add_turn(ConversationContext("Turn 2", "Response", "reminder"))
        self.memory.add_turn(ConversationContext("Turn 3", "Response", "weather"))
        
        weather_turns = self.memory.search_by_intent("weather")
        self.assertEqual(len(weather_turns), 2)

    def test_clear_memory(self) -> None:
        """Test clearing memory."""
        self.memory.add_turn(ConversationContext("Test", "Response", "test"))
        
        self.memory.clear()
        
        self.assertEqual(len(self.memory.get_turns()), 0)

    def test_memory_summary(self) -> None:
        """Test getting memory summary."""
        for i in range(3):
            self.memory.add_turn(ConversationContext(
                user_input=f"Query {i}",
                assistant_response=f"Answer {i}",
                intent="weather" if i % 2 == 0 else "reminder"
            ))
        
        summary = self.memory.get_summary()
        
        self.assertEqual(summary["total_turns"], 3)
        self.assertIn("intents", summary)


class TestStateTracker(unittest.TestCase):
    """Test conversation state management."""

    def setUp(self) -> None:
        self.tracker = StateTracker()

    def test_set_and_get_state(self) -> None:
        """Test setting and getting conversation state."""
        self.tracker.set_state("current_topic", "weather")
        
        value = self.tracker.get_state("current_topic")
        self.assertEqual(value, "weather")

    def test_state_with_any_type(self) -> None:
        """Test state can hold any type."""
        self.tracker.set_state("temp_data", {"key": "value", "numbers": [1, 2, 3]})
        
        data = self.tracker.get_state("temp_data")
        self.assertEqual(data["key"], "value")
        self.assertEqual(len(data["numbers"]), 3)

    def test_update_state(self) -> None:
        """Test updating state."""
        self.tracker.set_state("count", 1)
        self.tracker.set_state("count", 2)
        
        self.assertEqual(self.tracker.get_state("count"), 2)

    def test_state_existence_check(self) -> None:
        """Test checking if state exists."""
        self.tracker.set_state("exists", "yes")
        
        self.assertTrue(self.tracker.has_state("exists"))
        self.assertFalse(self.tracker.has_state("nonexistent"))

    def test_delete_state(self) -> None:
        """Test deleting state."""
        self.tracker.set_state("to_delete", "value")
        
        self.tracker.delete_state("to_delete")
        
        self.assertFalse(self.tracker.has_state("to_delete"))

    def test_clear_all_state(self) -> None:
        """Test clearing all state."""
        self.tracker.set_state("state1", "value1")
        self.tracker.set_state("state2", "value2")
        
        self.tracker.clear()
        
        self.assertFalse(self.tracker.has_state("state1"))
        self.assertFalse(self.tracker.has_state("state2"))

    def test_state_timeout(self) -> None:
        """Test state with expiration."""
        self.tracker.set_state("temp", "value", ttl=1)
        
        # Should exist immediately
        self.assertTrue(self.tracker.has_state("temp"))
        
        # Wait for timeout
        import time
        time.sleep(1.1)
        
        # Should be expired
        self.assertFalse(self.tracker.has_state("temp"))


class TestConversationManager(unittest.TestCase):
    """Test conversation state management."""

    def setUp(self) -> None:
        self.manager = ConversationManager()

    def test_start_conversation(self) -> None:
        """Test starting a conversation."""
        conv_id = self.manager.start_conversation("user123")
        
        self.assertIsNotNone(conv_id)
        self.assertTrue(self.manager.conversation_exists(conv_id))

    def test_add_exchange_to_conversation(self) -> None:
        """Test adding conversation exchange."""
        conv_id = self.manager.start_conversation("user456")
        
        self.manager.add_exchange(
            conv_id,
            user_input="Hi",
            assistant_response="Hello!",
            intent="greeting"
        )
        
        history = self.manager.get_conversation_history(conv_id)
        self.assertEqual(len(history), 1)

    def test_multi_turn_conversation(self) -> None:
        """Test multi-turn conversation tracking."""
        conv_id = self.manager.start_conversation("user789")
        
        # Turn 1
        self.manager.add_exchange(conv_id, "What time is it?", "It's 10am", "time")
        # Turn 2
        self.manager.add_exchange(conv_id, "Set a reminder", "Reminder set", "reminder")
        # Turn 3
        self.manager.add_exchange(conv_id, "When was it set?", "Just now", "reminder")
        
        history = self.manager.get_conversation_history(conv_id)
        self.assertEqual(len(history), 3)

    def test_get_last_intent(self) -> None:
        """Test getting last intent from conversation."""
        conv_id = self.manager.start_conversation("user001")
        
        self.manager.add_exchange(conv_id, "Query 1", "Answer 1", "weather")
        self.manager.add_exchange(conv_id, "Query 2", "Answer 2", "reminder")
        
        last_intent = self.manager.get_last_intent(conv_id)
        self.assertEqual(last_intent, "reminder")

    def test_search_conversation_by_intent(self) -> None:
        """Test searching conversation by intent."""
        conv_id = self.manager.start_conversation("user002")
        
        self.manager.add_exchange(conv_id, "Q1", "A1", "weather")
        self.manager.add_exchange(conv_id, "Q2", "A2", "reminder")
        self.manager.add_exchange(conv_id, "Q3", "A3", "weather")
        
        weather_turns = self.manager.search_conversation(conv_id, intent="weather")
        self.assertEqual(len(weather_turns), 2)

    def test_conversation_state(self) -> None:
        """Test managing conversation state."""
        conv_id = self.manager.start_conversation("user003")
        
        self.manager.set_conversation_state(conv_id, "topic", "weather")
        
        state = self.manager.get_conversation_state(conv_id, "topic")
        self.assertEqual(state, "weather")

    def test_end_conversation(self) -> None:
        """Test ending a conversation."""
        conv_id = self.manager.start_conversation("user004")
        self.manager.add_exchange(conv_id, "Hi", "Hi", "greeting")
        
        self.manager.end_conversation(conv_id)
        
        # Should still be accessible for history but marked as ended
        history = self.manager.get_conversation_history(conv_id)
        self.assertEqual(len(history), 1)

    def test_conversation_timeout(self) -> None:
        """Test conversation timeout and cleanup."""
        conv_id = self.manager.start_conversation("user005")
        
        # Manually age the conversation
        conv = self.manager.conversations[conv_id]
        conv["created_at"] = datetime.now() - timedelta(hours=25)
        
        # Cleanup should remove it
        self.manager.cleanup_old_conversations(hours=24)
        
        self.assertFalse(self.manager.conversation_exists(conv_id))

    def test_get_active_conversations(self) -> None:
        """Test getting active conversations."""
        conv1 = self.manager.start_conversation("user101")
        conv2 = self.manager.start_conversation("user102")
        
        active = self.manager.get_active_conversations()
        self.assertGreaterEqual(len(active), 2)

    def test_conversation_context_isolation(self) -> None:
        """Test that conversations are isolated from each other."""
        conv1 = self.manager.start_conversation("user201")
        conv2 = self.manager.start_conversation("user202")
        
        self.manager.set_conversation_state(conv1, "data", "conv1_value")
        self.manager.set_conversation_state(conv2, "data", "conv2_value")
        
        value1 = self.manager.get_conversation_state(conv1, "data")
        value2 = self.manager.get_conversation_state(conv2, "data")
        
        self.assertEqual(value1, "conv1_value")
        self.assertEqual(value2, "conv2_value")


if __name__ == "__main__":
    unittest.main()
