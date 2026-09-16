"""
Error handling utilities for the RAG Telegram bot.

This module provides error recovery mechanisms, retry logic, circuit breakers,
and comprehensive error context preservation for robust error handling.
"""

import asyncio
import functools
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import RAGError


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


@dataclass
class ErrorContext:
    """Comprehensive error context information."""

    error: Exception
    error_type: str
    error_message: str
    stack_trace: str
    timestamp: float
    component: str
    operation: str
    user_id: Optional[int] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_exception(
        cls,
        error: Exception,
        component: str,
        operation: str,
        user_id: Optional[int] = None,
        request_id: Optional[str] = None,
        **metadata: Any,
    ) -> "ErrorContext":
        """
        Create error context from an exception.

        Args:
            error: The exception that occurred
            component: Component where error occurred
            operation: Operation being performed
            user_id: Optional user ID
            request_id: Optional request ID
            **metadata: Additional metadata

        Returns:
            ErrorContext: Comprehensive error context
        """
        return cls(
            error=error,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            timestamp=time.time(),
            component=component,
            operation=operation,
            user_id=user_id,
            request_id=request_id,
            metadata=metadata,
        )


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_exceptions: List[Type[Exception]] = field(default_factory=list)
    non_retryable_exceptions: List[Type[Exception]] = field(default_factory=list)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3  # For half-open state
    timeout: float = 30.0


class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.

    Prevents cascade failures by temporarily stopping calls to failing services
    and allowing them time to recover.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.next_attempt_time = 0.0

        logger.info(f"Circuit breaker '{name}' initialized")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        current_time = time.time()

        # Check circuit state
        if self.state == CircuitBreakerState.OPEN:
            if current_time < self.next_attempt_time:
                raise RAGError(
                    f"Circuit breaker '{self.name}' is OPEN",
                    details={
                        "state": self.state.value,
                        "failure_count": self.failure_count,
                        "next_attempt_time": self.next_attempt_time,
                    },
                )
            else:
                # Try to recover
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")

        try:
            # Execute function with timeout
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=self.config.timeout
                )
            else:
                result = func(*args, **kwargs)

            # Success - update state
            await self._on_success()
            return result

        except asyncio.TimeoutError as e:
            await self._on_failure()
            raise RAGError(
                f"Circuit breaker '{self.name}' timeout", details=str(e)
            ) from e

        except Exception:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit breaker '{self.name}' recovered to CLOSED")
        else:
            self.failure_count = 0

    async def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.next_attempt_time = time.time() + self.config.recovery_timeout
            logger.warning(
                f"Circuit breaker '{self.name}' opened due to {self.failure_count} failures"
            )

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "next_attempt_time": self.next_attempt_time,
        }


class RetryHandler:
    """
    Retry handler with configurable strategies and error recovery.
    """

    def __init__(self, config: RetryConfig):
        """
        Initialize retry handler.

        Args:
            config: Retry configuration
        """
        self.config = config

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determine if an error should be retried.

        Args:
            error: Exception that occurred
            attempt: Current attempt number

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.config.max_attempts:
            return False

        # Check non-retryable exceptions
        if self.config.non_retryable_exceptions:
            for exc_type in self.config.non_retryable_exceptions:
                if isinstance(error, exc_type):
                    return False

        # Check retryable exceptions
        if self.config.retryable_exceptions:
            for exc_type in self.config.retryable_exceptions:
                if isinstance(error, exc_type):
                    return True
            return False  # Not in retryable list

        # Default: retry most errors except critical ones
        non_retryable_defaults = [
            ValueError,
            TypeError,
            AttributeError,
            ImportError,
            SyntaxError,
        ]

        for exc_type in non_retryable_defaults:
            if isinstance(error, exc_type):
                return False

        return True

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry attempt.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        if self.config.strategy == RetryStrategy.IMMEDIATE:
            delay = 0.0
        elif self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt
        else:  # EXPONENTIAL_BACKOFF
            delay = self.config.base_delay * (
                self.config.backoff_multiplier ** (attempt - 1)
            )

        # Apply max delay limit
        delay = min(delay, self.config.max_delay)

        # Add jitter to prevent thundering herd
        if self.config.jitter:
            import random

            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        component: str = "unknown",
        operation: str = "unknown",
        **kwargs,
    ) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            component: Component name for logging
            operation: Operation name for logging
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: Last exception if all retries failed
        """
        last_error = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                if attempt > 1:
                    logger.info(
                        f"Retry succeeded on attempt {attempt}",
                        component=component,
                        operation=operation,
                    )

                return result

            except Exception as e:
                last_error = e

                # Create error context
                error_context = ErrorContext.from_exception(
                    e,
                    component,
                    operation,
                    attempt=attempt,
                    max_attempts=self.config.max_attempts,
                )

                # Log error with context
                logger.error(
                    f"Attempt {attempt} failed: {str(e)}",
                    component=component,
                    operation=operation,
                    error_type=type(e).__name__,
                    attempt=attempt,
                    max_attempts=self.config.max_attempts,
                )

                # Check if should retry
                if not self.should_retry(e, attempt):
                    logger.error(
                        f"Not retrying due to error type: {type(e).__name__}",
                        component=component,
                        operation=operation,
                    )
                    raise

                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    logger.info(
                        f"Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{self.config.max_attempts})",
                        component=component,
                        operation=operation,
                    )
                    await asyncio.sleep(delay)

        # All retries failed
        logger.error(
            f"All {self.config.max_attempts} retry attempts failed",
            component=component,
            operation=operation,
            final_error=str(last_error),
        )

        if last_error:
            raise last_error


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry logic to functions.

    Args:
        config: Retry configuration (uses defaults if None)

    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        retry_handler = RetryHandler(config)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_handler.execute_with_retry(
                func,
                *args,
                component=func.__module__,
                operation=func.__name__,
                **kwargs,
            )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(
                retry_handler.execute_with_retry(
                    func,
                    *args,
                    component=func.__module__,
                    operation=func.__name__,
                    **kwargs,
                )
            )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def with_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """
    Decorator for adding circuit breaker protection to functions.

    Args:
        name: Circuit breaker name
        config: Circuit breaker configuration (uses defaults if None)

    Returns:
        Decorated function with circuit breaker protection
    """
    if config is None:
        config = CircuitBreakerConfig()

    circuit_breaker = CircuitBreaker(name, config)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await circuit_breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator


# Global circuit breakers for common services
openai_circuit_breaker = CircuitBreaker(
    "openai",
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0, timeout=30.0),
)

redis_circuit_breaker = CircuitBreaker(
    "redis",
    CircuitBreakerConfig(failure_threshold=5, recovery_timeout=10.0, timeout=5.0),
)

telegram_circuit_breaker = CircuitBreaker(
    "telegram",
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=15.0, timeout=10.0),
)
