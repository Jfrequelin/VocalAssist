"""
Resilience module for retry policies and circuit breaker patterns.
Provides strategies for handling failures and external service degradation.
"""

from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Type
import logging

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, block calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    
    max_retries: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    use_jitter: bool = True
    retry_on: list[Type[Exception]] = field(default_factory=lambda: [Exception])

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt.
        
        Args:
            attempt: Attempt number (1-indexed).
            
        Returns:
            Delay in seconds.
        """
        delay = self.initial_delay * (self.backoff_factor ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.use_jitter:
            # Add random jitter (±10%)
            jitter = delay * 0.1 * random.uniform(-1, 1)
            delay += jitter
        
        return max(0, delay)

    def should_retry(self, attempt: int) -> bool:
        """Check if should retry.
        
        Args:
            attempt: Current attempt number.
            
        Returns:
            True if should retry.
        """
        return attempt < self.max_retries

    def should_retry_on_error(self, error: Exception) -> bool:
        """Check if should retry on specific error.
        
        Args:
            error: The exception that occurred.
            
        Returns:
            True if should retry.
        """
        return any(isinstance(error, exc_type) for exc_type in self.retry_on)


class CircuitBreaker:
    """Circuit breaker for graceful degradation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ) -> None:
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures before opening circuit.
            recovery_timeout: Seconds before attempting recovery.
            success_threshold: Successes in half-open to close circuit.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()
        
        self.total_calls = 0
        self.total_success = 0
        self.total_failure = 0

    def allow_call(self) -> bool:
        """Check if call is allowed through circuit.
        
        Returns:
            True if call allowed.
        """
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has elapsed
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                    logger.info("Circuit breaker entering HALF_OPEN state")
                    return True
            return False
        
        # Half-open: allow call
        return True

    def call_succeeded(self) -> None:
        """Record successful call."""
        self.total_calls += 1
        self.total_success += 1
        
        if self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.last_state_change = datetime.now()
                logger.info("Circuit breaker CLOSED (recovered)")

    def call_failed(self) -> None:
        """Record failed call."""
        self.total_calls += 1
        self.total_failure += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.last_state_change = datetime.now()
                logger.warning(f"Circuit breaker OPEN (failures: {self.failure_count})")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.failure_count = 1
            logger.warning("Circuit breaker OPEN (during recovery attempt)")

    def reset(self) -> None:
        """Reset circuit breaker."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()
        logger.info("Circuit breaker reset")

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics.
        
        Returns:
            Dictionary with metrics.
        """
        if self.total_calls == 0:
            return {
                "state": self.state.value,
                "total_calls": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 1.0,
            }
        
        success_rate = self.total_success / self.total_calls
        
        return {
            "state": self.state.value,
            "total_calls": self.total_calls,
            "success_count": self.total_success,
            "failure_count": self.total_failure,
            "success_rate": success_rate,
        }


class ResilienceManager:
    """Manages resilience strategies (retry, circuit breaker, fallback)."""
    
    def __init__(self, adaptive_timeout: bool = False) -> None:
        """Initialize resilience manager.
        
        Args:
            adaptive_timeout: Enable adaptive timeout adjustment.
        """
        self.breakers: dict[str, CircuitBreaker] = {}
        self.adaptive_timeout = adaptive_timeout
        self.execution_times: dict[str, list[float]] = {}

    def register_breaker(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ) -> None:
        """Register circuit breaker for service.
        
        Args:
            service_name: Service identifier.
            failure_threshold: Failures before opening.
            recovery_timeout: Recovery timeout in seconds.
        """
        self.breakers[service_name] = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )

    def has_breaker(self, service_name: str) -> bool:
        """Check if breaker exists for service.
        
        Args:
            service_name: Service identifier.
            
        Returns:
            True if breaker registered.
        """
        return service_name in self.breakers

    def execute(
        self,
        service_name: str,
        operation: Callable[[], Any],
    ) -> Any:
        """Execute operation with circuit breaker protection.
        
        Args:
            service_name: Service identifier.
            operation: Callable to execute.
            
        Returns:
            Operation result.
            
        Raises:
            Exception if circuit open or operation fails.
        """
        breaker = self.breakers.get(service_name)
        
        if breaker and not breaker.allow_call():
            raise Exception(f"Circuit breaker open for {service_name}")
        
        start_time = time.time()
        try:
            result = operation()
            if breaker:
                breaker.call_succeeded()
            return result
        except Exception:
            if breaker:
                breaker.call_failed()
            raise
        finally:
            elapsed = time.time() - start_time
            if self.adaptive_timeout and service_name:
                self._record_time(service_name, elapsed)

    def execute_with_retry(
        self,
        service_name: str,
        operation: Callable[[], Any],
        retry_policy: Optional[RetryPolicy] = None,
    ) -> Any:
        """Execute with automatic retry.
        
        Args:
            service_name: Service identifier.
            operation: Callable to execute.
            retry_policy: Retry configuration.
            
        Returns:
            Operation result.
        """
        if retry_policy is None:
            retry_policy = RetryPolicy()
        
        attempt = 1
        last_error = None
        
        while attempt <= retry_policy.max_retries:
            try:
                return self.execute(service_name, operation)
            except Exception as e:
                last_error = e
                
                if not retry_policy.should_retry(attempt):
                    break
                
                if not retry_policy.should_retry_on_error(e):
                    break
                
                delay = retry_policy.get_delay(attempt)
                logger.info(f"Retry {attempt} for {service_name} after {delay}s")
                time.sleep(delay)
                attempt += 1
        
        if last_error:
            raise last_error
        return None

    def execute_with_fallback(
        self,
        service_name: str,
        operation: Callable[[], Any],
        fallback: Callable[[], Any],
    ) -> Any:
        """Execute with fallback on failure.
        
        Args:
            service_name: Service identifier.
            operation: Primary operation.
            fallback: Fallback operation.
            
        Returns:
            Result from primary or fallback.
        """
        try:
            return self.execute(service_name, operation)
        except Exception as e:
            logger.warning(f"Primary operation failed for {service_name}, using fallback: {e}")
            return fallback()

    def execute_with_timeout(
        self,
        service_name: str,
        operation: Callable[[], Any],
        timeout: float = 30.0,
    ) -> Optional[Any]:
        """Execute with timeout.
        
        Args:
            service_name: Service identifier.
            operation: Callable to execute.
            timeout: Timeout in seconds.
            
        Returns:
            Operation result or None on timeout.
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.execute, service_name, operation)
            try:
                return future.result(timeout=timeout)
            except FutureTimeoutError:
                logger.warning(f"Operation timed out: {service_name}")
                return None

    def record_execution_time(self, service_name: str, duration: float) -> None:
        """Record execution time for adaptive timeout.
        
        Args:
            service_name: Service identifier.
            duration: Execution time in seconds.
        """
        if service_name not in self.execution_times:
            self.execution_times[service_name] = []
        
        self.execution_times[service_name].append(duration)
        
        # Keep only recent 100 measurements
        if len(self.execution_times[service_name]) > 100:
            self.execution_times[service_name] = self.execution_times[service_name][-100:]

    def get_adaptive_timeout(self, service_name: str) -> float:
        """Get adaptive timeout based on historical performance.
        
        Args:
            service_name: Service identifier.
            
        Returns:
            Recommended timeout in seconds.
        """
        if service_name not in self.execution_times:
            return 30.0
        
        times = self.execution_times[service_name]
        if not times:
            return 30.0
        
        avg_time = sum(times) / len(times)
        # Use average + 2 * standard deviation + 5s margin
        return min(avg_time * 2 + 5, 60)

    def _record_time(self, service_name: str, duration: float) -> None:
        """Internal method to record execution time."""
        self.record_execution_time(service_name, duration)

    def get_resilience_stats(self) -> dict[str, Any]:
        """Get resilience statistics.
        
        Returns:
            Dictionary with stats.
        """
        total_ops = 0
        total_success = 0
        total_failure = 0
        
        breaker_states: dict[str, str] = {}
        for name, breaker in self.breakers.items():
            metrics = breaker.get_metrics()
            total_ops += metrics["total_calls"]
            total_success += metrics["success_count"]
            total_failure += metrics["failure_count"]
            breaker_states[name] = metrics["state"]
        
        return {
            "total_operations": total_ops,
            "total_success": total_success,
            "total_failure": total_failure,
            "breaker_states": breaker_states,
        }
