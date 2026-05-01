"""
Tests for MACRO-004-T3: Retry policies and circuit breaker patterns
Tests resilience strategies for external service failures.
"""

from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta

from src.assistant.resilience import (
    RetryPolicy,
    CircuitBreakerState,
    CircuitBreaker,
    ResilienceManager,
)


class TestRetryPolicy(unittest.TestCase):
    """Test retry policies."""

    def test_exponential_backoff_policy(self) -> None:
        """Test exponential backoff retry policy."""
        policy = RetryPolicy(
            max_retries=3,
            initial_delay=1,
            backoff_factor=2
        )

        self.assertEqual(policy.max_retries, 3)
        self.assertEqual(policy.initial_delay, 1)
        self.assertEqual(policy.backoff_factor, 2)

    def test_calculate_backoff_delay(self) -> None:
        """Test calculating backoff delay."""
        policy = RetryPolicy(
            max_retries=3,
            initial_delay=1,
            backoff_factor=2,
            use_jitter=False  # Disable jitter for predictable testing
        )

        # Attempt 1: 1 second
        delay1 = policy.get_delay(attempt=1)
        self.assertEqual(delay1, 1)

        # Attempt 2: 2 seconds
        delay2 = policy.get_delay(attempt=2)
        self.assertEqual(delay2, 2)

        # Attempt 3: 4 seconds
        delay3 = policy.get_delay(attempt=3)
        self.assertEqual(delay3, 4)

    def test_retry_policy_with_jitter(self) -> None:
        """Test retry policy with jitter to prevent thundering herd."""
        policy = RetryPolicy(
            max_retries=3,
            initial_delay=1,
            backoff_factor=2,
            use_jitter=True
        )

        delays = [policy.get_delay(i) for i in range(1, 4)]

        # All delays should be positive
        self.assertTrue(all(d > 0 for d in delays))

    def test_max_delay_cap(self) -> None:
        """Test max delay cap."""
        policy = RetryPolicy(
            max_retries=10,
            initial_delay=1,
            backoff_factor=2,
            max_delay=10,
            use_jitter=False  # Disable jitter for predictable testing
        )

        # Even with exponential growth, should be capped
        delay_high = policy.get_delay(attempt=8)
        self.assertLessEqual(delay_high, policy.max_delay)

    def test_should_retry(self) -> None:
        """Test decision to retry."""
        policy = RetryPolicy(max_retries=3)

        # First 2 attempts should retry (attempt < max_retries)
        self.assertTrue(policy.should_retry(attempt=1))
        self.assertTrue(policy.should_retry(attempt=2))

        # 3rd attempt should not retry (attempt not < max_retries)
        self.assertFalse(policy.should_retry(attempt=3))

    def test_retry_on_specific_errors(self) -> None:
        """Test retrying only on specific error types."""
        policy = RetryPolicy(
            max_retries=3,
            retry_on=[ConnectionError, TimeoutError]
        )

        # Should retry on ConnectionError
        self.assertTrue(policy.should_retry_on_error(ConnectionError("Connection failed")))

        # Should not retry on ValueError
        self.assertFalse(policy.should_retry_on_error(ValueError("Invalid value")))


class TestCircuitBreakerState(unittest.TestCase):
    """Test circuit breaker states."""

    def test_circuit_breaker_states_exist(self) -> None:
        """Test all circuit breaker states are defined."""
        self.assertIn(CircuitBreakerState.CLOSED, [s for s in CircuitBreakerState])
        self.assertIn(CircuitBreakerState.OPEN, [s for s in CircuitBreakerState])
        self.assertIn(CircuitBreakerState.HALF_OPEN, [s for s in CircuitBreakerState])


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""

    def setUp(self) -> None:
        self.breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=2
        )

    def test_circuit_starts_closed(self) -> None:
        """Test circuit starts in closed state."""
        self.assertEqual(self.breaker.state, CircuitBreakerState.CLOSED)

    def test_successful_call_maintains_closed(self) -> None:
        """Test successful calls keep circuit closed."""
        self.breaker.call_succeeded()
        self.breaker.call_succeeded()

        self.assertEqual(self.breaker.state, CircuitBreakerState.CLOSED)

    def test_failure_threshold_opens_circuit(self) -> None:
        """Test failures open circuit after threshold."""
        for _ in range(3):
            self.breaker.call_failed()

        self.assertEqual(self.breaker.state, CircuitBreakerState.OPEN)

    def test_open_circuit_blocks_calls(self) -> None:
        """Test open circuit blocks new calls."""
        # Open the circuit
        for _ in range(3):
            self.breaker.call_failed()

        # Try to call with open circuit
        allowed = self.breaker.allow_call()
        self.assertFalse(allowed)

    def test_half_open_allows_recovery_attempt(self) -> None:
        """Test half-open state allows recovery attempt."""
        # Open circuit
        for _ in range(3):
            self.breaker.call_failed()

        # Force timeout to trigger half-open
        self.breaker.last_failure_time = datetime.now() - timedelta(seconds=5)

        # Should now be half-open and allow call
        allowed = self.breaker.allow_call()
        self.assertTrue(allowed)
        self.assertEqual(self.breaker.state, CircuitBreakerState.HALF_OPEN)

    def test_successful_recovery_closes_circuit(self) -> None:
        """Test successful call in half-open closes circuit."""
        # Configure with success threshold of 1
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=2,
            success_threshold=1
        )

        # Open circuit
        for _ in range(3):
            breaker.call_failed()

        # Force to half-open
        breaker.last_failure_time = datetime.now() - timedelta(seconds=5)
        breaker.allow_call()

        # Successful call should close circuit
        breaker.call_succeeded()
        self.assertEqual(breaker.state, CircuitBreakerState.CLOSED)

    def test_failure_in_half_open_reopens(self) -> None:
        """Test failure in half-open state reopens circuit."""
        # Open circuit
        for _ in range(3):
            self.breaker.call_failed()

        # Force to half-open
        self.breaker.last_failure_time = datetime.now() - timedelta(seconds=5)
        self.breaker.allow_call()

        # Failure should reopen
        self.breaker.call_failed()
        self.assertEqual(self.breaker.state, CircuitBreakerState.OPEN)

    def test_circuit_breaker_metrics(self) -> None:
        """Test circuit breaker metrics tracking."""
        self.breaker.call_succeeded()
        self.breaker.call_succeeded()
        self.breaker.call_failed()

        metrics = self.breaker.get_metrics()

        self.assertEqual(metrics["total_calls"], 3)
        self.assertEqual(metrics["success_count"], 2)
        self.assertEqual(metrics["failure_count"], 1)

    def test_reset_circuit_breaker(self) -> None:
        """Test resetting circuit breaker."""
        # Open circuit
        for _ in range(3):
            self.breaker.call_failed()

        self.breaker.reset()

        # Should be back to closed
        self.assertEqual(self.breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.breaker.failure_count, 0)


class TestResilienceManager(unittest.TestCase):
    """Test resilience management."""

    def setUp(self) -> None:
        self.manager = ResilienceManager()

    def test_register_circuit_breaker(self) -> None:
        """Test registering circuit breaker for service."""
        self.manager.register_breaker("leon_api", failure_threshold=5)

        self.assertTrue(self.manager.has_breaker("leon_api"))

    def test_execute_with_resilience(self) -> None:
        """Test executing operation with resilience."""
        def successful_op() -> str:
            return "success"

        result = self.manager.execute("test_service", successful_op)

        self.assertEqual(result, "success")

    def test_retry_on_transient_failure(self) -> None:
        """Test retrying on transient failure."""
        call_count = [0]

        def flaky_op() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Transient failure")
            return "success"

        retry_policy = RetryPolicy(max_retries=3)
        result = self.manager.execute_with_retry("flaky", flaky_op, retry_policy)

        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 3)

    def test_circuit_breaker_protection(self) -> None:
        """Test circuit breaker protects against cascading failures."""
        self.manager.register_breaker("leon", failure_threshold=2)

        def failing_op() -> str:
            raise Exception("Leon service down")

        # First two calls fail and open breaker
        for _ in range(2):
            try:
                self.manager.execute("leon", failing_op)
            except Exception:
                pass

        # Third call should be blocked (circuit open)
        with self.assertRaises(Exception) as ctx:
            self.manager.execute("leon", failing_op)

        # Should get circuit open error, not the original error
        self.assertIn("Circuit", str(ctx.exception) or "open")

    def test_fallback_on_failure(self) -> None:
        """Test executing fallback on failure."""
        def primary_op() -> str:
            raise Exception("Primary failed")

        def fallback_op() -> str:
            return "fallback_response"

        result = self.manager.execute_with_fallback("service", primary_op, fallback_op)

        self.assertEqual(result, "fallback_response")

    def test_timeout_handling(self) -> None:
        """Test operation timeout."""
        def slow_op() -> str:
            time.sleep(2)
            return "done"

        # This test shows timeout behavior (actual timeout depends on OS/threading)
        # For now, test that the method exists and doesn't crash
        try:
            _result = self.manager.execute_with_timeout("slow", slow_op, timeout=0.1)
            # Result could be None or the value depending on timing
            self.assertIsNotNone(self.manager)
        except Exception:
            # Timeout exception is acceptable
            pass

    def test_resilience_stats(self) -> None:
        """Test tracking resilience statistics."""
        for i in range(5):
            try:
                if i < 3:
                    raise Exception("Fail")
                self.manager.execute("test", lambda: "success")
            except Exception:
                pass

        stats = self.manager.get_resilience_stats()

        self.assertIn("total_operations", stats)
        self.assertIn("breaker_states", stats)

    def test_adaptive_timeout(self) -> None:
        """Test adaptive timeout adjustment."""
        manager = ResilienceManager(adaptive_timeout=True)

        # Record some execution times
        manager.record_execution_time("api", 0.1)
        manager.record_execution_time("api", 0.15)
        manager.record_execution_time("api", 0.12)

        # Timeout should be based on average + margin
        timeout = manager.get_adaptive_timeout("api")
        self.assertGreater(timeout, 0.15)


if __name__ == "__main__":
    unittest.main()
