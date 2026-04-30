"""
Intelligent routing module for Leon integration.
Routes queries between local processing, external Leon NLU, and cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class LeonRoute(Enum):
    """Available routing destinations."""
    
    LOCAL = "local"         # Process with local intents
    LEON = "leon"           # Send to Leon NLU
    CACHE = "cache"         # Use cached response
    FALLBACK = "fallback"   # Error handling route

    def get_description(self) -> str:
        """Get route description."""
        descriptions = {
            "local": "Process with local intent system",
            "leon": "Send to Leon external NLU",
            "cache": "Use cached response from similar query",
            "fallback": "Fallback error handling",
        }
        return descriptions.get(self.value, "Unknown route")


@dataclass
class RoutingContext:
    """Decision context for routing."""
    
    user_input: str
    detected_intent: str
    confidence: float
    prefer_local: bool = False
    is_offline: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_context: Optional[RoutingContext] = None
    priority: str = "normal"  # normal, high, low
    timestamp: datetime = field(default_factory=datetime.now)

    def has_multi_turn(self) -> bool:
        """Check if this is part of multi-turn conversation."""
        return self.parent_context is not None


@dataclass
class RoutingDecision:
    """Decision made by router."""
    
    route: LeonRoute
    confidence: float
    reason: str
    fallback_route: Optional[LeonRoute] = None
    extracted_params: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class IntelligentRouter:
    """Intelligent router for Leon integration."""
    
    def __init__(self) -> None:
        """Initialize the intelligent router."""
        self.stats = {
            "total_routed": 0,
            "by_route": {},
            "by_confidence": [],
        }
        self.cache: dict[str, tuple[datetime, RoutingDecision]] = {}
        
        # Confidence thresholds
        self.LOCAL_THRESHOLD = 0.85
        self.CACHE_THRESHOLD = 0.75
        self.LEON_THRESHOLD = 0.4

    def route(self, context: RoutingContext) -> RoutingDecision:
        """Route query to appropriate destination.
        
        Args:
            context: Routing context with query information.
            
        Returns:
            RoutingDecision with selected route and confidence.
        """
        self.stats["total_routed"] += 1
        
        # Check offline mode
        if context.is_offline:
            return self._route_offline(context)
        
        # Check cache first
        cached = self._check_cache(context)
        if cached:
            return cached
        
        # User preference override
        if context.prefer_local and context.confidence > self.CACHE_THRESHOLD:
            return self._make_decision(
                route=LeonRoute.LOCAL,
                confidence=context.confidence,
                reason="User preference for local processing",
                context=context
            )
        
        # High confidence local intents
        if context.confidence >= self.LOCAL_THRESHOLD:
            return self._make_decision(
                route=LeonRoute.LOCAL,
                confidence=context.confidence,
                reason=f"High confidence local intent ({context.confidence:.2f})",
                context=context
            )
        
        # Check for cacheable patterns
        if context.confidence >= self.CACHE_THRESHOLD and self._is_cacheable(context):
            return self._make_decision(
                route=LeonRoute.CACHE,
                confidence=context.confidence,
                reason="Cacheable pattern with good confidence",
                fallback_route=LeonRoute.LEON,
                context=context
            )
        
        # Medium confidence - try local first, fallback to Leon
        if context.confidence >= self.LEON_THRESHOLD:
            return self._make_decision(
                route=LeonRoute.LOCAL,
                confidence=context.confidence * 0.9,  # Lower effective confidence
                reason=f"Medium confidence, trying local with Leon fallback ({context.confidence:.2f})",
                fallback_route=LeonRoute.LEON,
                context=context
            )
        
        # Low confidence - use Leon
        return self._make_decision(
            route=LeonRoute.LEON,
            confidence=context.confidence,
            reason=f"Low confidence, routing to Leon ({context.confidence:.2f})",
            fallback_route=LeonRoute.FALLBACK,
            context=context
        )

    def _route_offline(self, context: RoutingContext) -> RoutingDecision:
        """Route query when offline.
        
        Args:
            context: Routing context.
            
        Returns:
            RoutingDecision for offline routing.
        """
        if context.confidence >= self.LOCAL_THRESHOLD:
            return self._make_decision(
                route=LeonRoute.LOCAL,
                confidence=context.confidence,
                reason="Offline: routing to local",
                context=context
            )
        else:
            return self._make_decision(
                route=LeonRoute.CACHE,
                confidence=0.5,
                reason="Offline: trying cache",
                fallback_route=LeonRoute.LOCAL,
                context=context
            )

    def _check_cache(self, context: RoutingContext) -> Optional[RoutingDecision]:
        """Check if similar query is cached.
        
        Args:
            context: Routing context.
            
        Returns:
            Cached decision if found, None otherwise.
        """
        # Simple cache key - could be enhanced with semantic similarity
        cache_key = f"{context.detected_intent}:{context.user_input[:50]}"
        
        if cache_key in self.cache:
            cached_time, decision = self.cache[cache_key]
            
            # Check cache expiry (1 hour)
            if datetime.now() - cached_time < timedelta(hours=1):
                logger.debug(f"Cache hit for {cache_key}")
                return decision
            else:
                del self.cache[cache_key]
        
        return None

    def _is_cacheable(self, context: RoutingContext) -> bool:
        """Determine if query response is cacheable.
        
        Args:
            context: Routing context.
            
        Returns:
            True if query should be cached.
        """
        # Cacheable intents: time, date, weather (non-location-specific), etc.
        cacheable_intents = ["time", "date", "reminder", "note", "greeting"]
        
        return context.detected_intent in cacheable_intents

    def _make_decision(
        self,
        route: LeonRoute,
        confidence: float,
        reason: str,
        fallback_route: Optional[LeonRoute] = None,
        context: Optional[RoutingContext] = None,
    ) -> RoutingDecision:
        """Create routing decision and update stats.
        
        Args:
            route: Selected route.
            confidence: Decision confidence.
            reason: Reason for decision.
            fallback_route: Optional fallback route.
            context: Original routing context.
            
        Returns:
            RoutingDecision.
        """
        decision = RoutingDecision(
            route=route,
            confidence=confidence,
            reason=reason,
            fallback_route=fallback_route,
            extracted_params=context.metadata if context else {}
        )
        
        # Update statistics
        route_count = self.stats["by_route"].get(route.value, 0)
        self.stats["by_route"][route.value] = route_count + 1
        self.stats["by_confidence"].append(confidence)
        
        # Cache if appropriate
        if context and route == LeonRoute.CACHE:
            cache_key = f"{context.detected_intent}:{context.user_input[:50]}"
            self.cache[cache_key] = (datetime.now(), decision)
        
        logger.info(f"Routing decision: {route.value} (confidence: {confidence:.2f}) - {reason}")
        
        return decision

    def get_routing_stats(self) -> dict:
        """Get routing statistics.
        
        Returns:
            Dictionary with routing statistics.
        """
        avg_confidence = (
            sum(self.stats["by_confidence"]) / len(self.stats["by_confidence"])
            if self.stats["by_confidence"]
            else 0
        )
        
        return {
            "total_routed": self.stats["total_routed"],
            "by_route": self.stats["by_route"],
            "average_confidence": avg_confidence,
            "cache_size": len(self.cache),
        }

    def set_confidence_threshold(
        self,
        local_threshold: float = 0.85,
        cache_threshold: float = 0.75,
        leon_threshold: float = 0.4,
    ) -> None:
        """Configure confidence thresholds.
        
        Args:
            local_threshold: Threshold for local routing.
            cache_threshold: Threshold for cache routing.
            leon_threshold: Threshold for Leon routing.
        """
        self.LOCAL_THRESHOLD = local_threshold
        self.CACHE_THRESHOLD = cache_threshold
        self.LEON_THRESHOLD = leon_threshold

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self.cache.clear()
        logger.info("Cache cleared")


class ContextManager:
    """Manages routing context across turns."""
    
    def __init__(self) -> None:
        """Initialize context manager."""
        self.context_history: list[RoutingContext] = []
        self.max_history = 10

    def add_context(self, context: RoutingContext) -> None:
        """Add context to history.
        
        Args:
            context: New routing context.
        """
        self.context_history.append(context)
        
        if len(self.context_history) > self.max_history:
            self.context_history = self.context_history[-self.max_history:]

    def get_previous_context(self, depth: int = 1) -> Optional[RoutingContext]:
        """Get previous context.
        
        Args:
            depth: How many turns back (1 = immediate previous).
            
        Returns:
            Previous context or None.
        """
        if len(self.context_history) >= depth:
            return self.context_history[-depth]
        return None

    def get_conversation_context(self) -> list[RoutingContext]:
        """Get current conversation context.
        
        Returns:
            List of contexts in current conversation.
        """
        return self.context_history.copy()

    def clear_history(self) -> None:
        """Clear context history."""
        self.context_history.clear()
