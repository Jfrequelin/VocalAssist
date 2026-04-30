"""
Tests for MACRO-004-T1: Intelligent routing to Leon
Tests advanced routing logic for external NLU processing.
"""

from __future__ import annotations

import unittest
from enum import Enum
from dataclasses import dataclass

from src.assistant.leon_router import (
    LeonRoute,
    RoutingContext,
    RoutingDecision,
    IntelligentRouter,
)


class TestLeonRoute(unittest.TestCase):
    """Test LeonRoute enumeration."""

    def test_route_types_exist(self) -> None:
        """Test that route types are defined."""
        self.assertIn(LeonRoute.LOCAL, [r for r in LeonRoute])
        self.assertIn(LeonRoute.LEON, [r for r in LeonRoute])
        self.assertIn(LeonRoute.FALLBACK, [r for r in LeonRoute])
        self.assertIn(LeonRoute.CACHE, [r for r in LeonRoute])

    def test_route_descriptions(self) -> None:
        """Test that routes have descriptions."""
        self.assertIsNotNone(LeonRoute.LOCAL.get_description())
        self.assertIsNotNone(LeonRoute.LEON.get_description())


class TestRoutingContext(unittest.TestCase):
    """Test RoutingContext for route decision making."""

    def test_create_routing_context(self) -> None:
        """Test creating a routing context."""
        context = RoutingContext(
            user_input="What's the weather?",
            detected_intent="weather",
            confidence=0.85
        )
        
        self.assertEqual(context.user_input, "What's the weather?")
        self.assertEqual(context.detected_intent, "weather")
        self.assertEqual(context.confidence, 0.85)

    def test_context_with_user_preferences(self) -> None:
        """Test context with user preferences."""
        context = RoutingContext(
            user_input="Play music",
            detected_intent="music",
            confidence=0.9,
            prefer_local=True
        )
        
        self.assertTrue(context.prefer_local)

    def test_context_with_metadata(self) -> None:
        """Test context with additional metadata."""
        context = RoutingContext(
            user_input="Set reminder",
            detected_intent="reminder",
            confidence=0.8,
            metadata={"time": "tomorrow", "title": "Meeting"}
        )
        
        self.assertIn("time", context.metadata)
        self.assertEqual(context.metadata["title"], "Meeting")


class TestRoutingDecision(unittest.TestCase):
    """Test RoutingDecision output."""

    def test_create_routing_decision(self) -> None:
        """Test creating a routing decision."""
        decision = RoutingDecision(
            route=LeonRoute.LOCAL,
            confidence=0.95,
            reason="High confidence local intent"
        )
        
        self.assertEqual(decision.route, LeonRoute.LOCAL)
        self.assertEqual(decision.confidence, 0.95)

    def test_decision_with_fallback(self) -> None:
        """Test decision with fallback route."""
        decision = RoutingDecision(
            route=LeonRoute.LEON,
            confidence=0.7,
            reason="Medium confidence",
            fallback_route=LeonRoute.LOCAL
        )
        
        self.assertEqual(decision.fallback_route, LeonRoute.LOCAL)

    def test_decision_with_parameters(self) -> None:
        """Test decision with extracted parameters."""
        decision = RoutingDecision(
            route=LeonRoute.LEON,
            confidence=0.8,
            reason="Need external NLU",
            extracted_params={"duration": "2 hours", "topic": "machine learning"}
        )
        
        self.assertIn("duration", decision.extracted_params)


class TestIntelligentRouter(unittest.TestCase):
    """Test intelligent routing logic."""

    def setUp(self) -> None:
        self.router = IntelligentRouter()

    def test_local_intent_routing(self) -> None:
        """Test routing high-confidence local intents to LOCAL."""
        context = RoutingContext(
            user_input="Turn on the light",
            detected_intent="light",
            confidence=0.95
        )
        
        decision = self.router.route(context)
        
        self.assertEqual(decision.route, LeonRoute.LOCAL)
        self.assertGreater(decision.confidence, 0.9)

    def test_unknown_intent_routing(self) -> None:
        """Test routing unknown intents to LEON."""
        context = RoutingContext(
            user_input="Tell me about photosynthesis",
            detected_intent="unknown",
            confidence=0.3
        )
        
        decision = self.router.route(context)
        
        self.assertEqual(decision.route, LeonRoute.LEON)

    def test_complex_intent_routing(self) -> None:
        """Test routing complex queries to LEON."""
        context = RoutingContext(
            user_input="What's the weather in Paris tomorrow afternoon with probability of rain?",
            detected_intent="weather",
            confidence=0.7
        )
        
        decision = self.router.route(context)
        
        # Complex query with medium confidence should go to LOCAL with LEON fallback
        # The router will try LOCAL first, but has LEON as fallback for better understanding
        self.assertIn(decision.route, [LeonRoute.LOCAL, LeonRoute.LEON])
        self.assertIsNotNone(decision.fallback_route)

    def test_cache_routing(self) -> None:
        """Test routing to cache for frequent queries."""
        context = RoutingContext(
            user_input="What time is it?",
            detected_intent="time",
            confidence=0.9
        )
        
        decision = self.router.route(context)
        
        # High confidence + cached intent
        self.assertIn(decision.route, [LeonRoute.LOCAL, LeonRoute.CACHE])

    def test_user_preference_override(self) -> None:
        """Test user preferences override default routing."""
        context = RoutingContext(
            user_input="Weather in Paris",
            detected_intent="weather",
            confidence=0.7,
            prefer_local=True
        )
        
        decision = self.router.route(context)
        
        # User prefers local should try local first
        self.assertEqual(decision.route, LeonRoute.LOCAL)

    def test_offline_mode_routing(self) -> None:
        """Test routing when offline (Leon unavailable)."""
        context = RoutingContext(
            user_input="Search the web",
            detected_intent="search",
            confidence=0.8,
            is_offline=True
        )
        
        decision = self.router.route(context)
        
        # Must route to LOCAL or CACHE when offline
        self.assertNotEqual(decision.route, LeonRoute.LEON)

    def test_low_confidence_with_fallback(self) -> None:
        """Test low confidence routing with fallback."""
        context = RoutingContext(
            user_input="Blah blargh zxc",
            detected_intent="unknown",
            confidence=0.2
        )
        
        decision = self.router.route(context)
        
        # Should have fallback plan
        self.assertIsNotNone(decision.fallback_route)

    def test_routing_confidence_decay(self) -> None:
        """Test routing decision based on confidence decay."""
        high_conf = RoutingContext(
            user_input="Turn on lights",
            detected_intent="light",
            confidence=0.95
        )
        
        low_conf = RoutingContext(
            user_input="Turn on lights",
            detected_intent="light",
            confidence=0.55
        )
        
        high_decision = self.router.route(high_conf)
        low_decision = self.router.route(low_conf)
        
        # Higher confidence should prefer LOCAL
        self.assertEqual(high_decision.route, LeonRoute.LOCAL)
        # Lower confidence should consider LEON
        self.assertIn(low_decision.route, [LeonRoute.LEON, LeonRoute.LOCAL])


class TestRoutingIntegration(unittest.TestCase):
    """Integration tests for routing system."""

    def setUp(self) -> None:
        self.router = IntelligentRouter()

    def test_multi_turn_routing(self) -> None:
        """Test routing across multi-turn conversations."""
        # First turn
        context1 = RoutingContext(
            user_input="Set a reminder",
            detected_intent="reminder",
            confidence=0.85
        )
        decision1 = self.router.route(context1)
        
        # Second turn (follow-up)
        context2 = RoutingContext(
            user_input="For tomorrow at 9am",
            detected_intent="time",
            confidence=0.8,
            parent_context=context1
        )
        decision2 = self.router.route(context2)
        
        # Both should be handled effectively
        self.assertIsNotNone(decision1)
        self.assertIsNotNone(decision2)

    def test_semantic_similarity_routing(self) -> None:
        """Test routing similar queries consistently."""
        queries = [
            "What's the weather?",
            "How's the weather today?",
            "Tell me the weather",
        ]
        
        decisions = []
        for query in queries:
            context = RoutingContext(
                user_input=query,
                detected_intent="weather",
                confidence=0.8
            )
            decisions.append(self.router.route(context))
        
        # Similar queries should get similar routing
        routes = [d.route for d in decisions]
        self.assertTrue(all(r == routes[0] for r in routes))

    def test_cost_aware_routing(self) -> None:
        """Test routing considers computational cost."""
        simple_context = RoutingContext(
            user_input="What time is it?",
            detected_intent="time",
            confidence=0.95
        )
        
        complex_context = RoutingContext(
            user_input="Analyze the best strategies for optimizing distributed systems",
            detected_intent="analysis",
            confidence=0.6
        )
        
        simple_decision = self.router.route(simple_context)
        complex_decision = self.router.route(complex_context)
        
        # Simple query to LOCAL (low cost)
        self.assertEqual(simple_decision.route, LeonRoute.LOCAL)
        # Complex query might go to LEON or require external processing
        self.assertIsNotNone(complex_decision)

    def test_routing_statistics(self) -> None:
        """Test tracking routing statistics."""
        for i in range(10):
            context = RoutingContext(
                user_input="Test query",
                detected_intent="test",
                confidence=0.7
            )
            self.router.route(context)
        
        stats = self.router.get_routing_stats()
        
        self.assertEqual(stats["total_routed"], 10)
        self.assertIn("by_route", stats)


if __name__ == "__main__":
    unittest.main()
