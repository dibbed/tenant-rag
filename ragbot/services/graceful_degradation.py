"""
Graceful degradation service for the RAG Telegram bot.

This module provides graceful degradation capabilities that allow the system
to continue operating with reduced functionality when components fail.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, List

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.error_handling import CircuitBreaker, CircuitBreakerConfig, ErrorContext


class ServiceStatus(Enum):
    """Service status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""

    enabled: bool = True
    timeout: float = 5.0
    max_retries: int = 2
    fallback_message: Optional[str] = None
    cache_fallback: bool = True
    offline_mode: bool = False


@dataclass
class ServiceHealth:
    """Health information for a service."""

    name: str
    status: ServiceStatus
    last_check: float
    error_count: int
    success_count: int
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    fallback_active: bool = False


class GracefulDegradationService:
    """
    Service for managing graceful degradation across the RAG system.

    This service monitors component health and provides fallback mechanisms
    when services fail, ensuring the system continues to operate with
    reduced functionality rather than complete failure.
    """

    def __init__(self):
        """Initialize the graceful degradation service."""
        self.services: Dict[str, ServiceHealth] = {}
        self.fallback_configs: Dict[str, FallbackConfig] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.fallback_counts: Dict[str, int] = {}
        self.timeouts_registry: Dict[str, float] = {}

        # Initialize default services
        self._initialize_default_services()

        # Load timeouts registry from settings if available
        self._load_timeouts_from_settings()

        logger.info("Graceful degradation service initialized")

    def _load_timeouts_from_settings(self) -> None:
        """Load per-service timeouts from settings.timeouts if available."""
        try:
            to = getattr(settings, "timeouts", object())
            self.timeouts_registry = {
                "openai": float(getattr(to, "openai_timeout_sec", 30.0)),
                "redis": float(getattr(to, "redis_timeout_sec", 5.0)),
                "vector_store": float(getattr(to, "vector_search_timeout_sec", 10.0)),
            }
        except Exception:
            self.timeouts_registry = {}

    def _get_timeout_for(self, service_name: str, default: float) -> float:
        """Return configured timeout for service or fallback to default."""
        return float(self.timeouts_registry.get(service_name, default))

    def _inc_fallback(self, service_name: str) -> None:
        """Increment fallback counter for metrics."""
        self.fallback_counts[service_name] = (
            self.fallback_counts.get(service_name, 0) + 1
        )

    def get_fallback_metrics(self) -> Dict[str, int]:
        """Expose fallback counts by service for telemetry."""
        return dict(self.fallback_counts)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics for all services."""
        metrics = {
            "services_count": len(self.services),
            "fallback_counts": dict(self.fallback_counts),
            "timeouts_registry": dict(self.timeouts_registry),
            "service_health_summary": {},
            "circuit_breaker_status": {},
            "overall_system_health": self.get_system_status(),
        }

        # Calculate average response time and success rate per service
        for service_name, service in self.services.items():
            total_calls = service.success_count + service.error_count
            success_rate = (
                service.success_count / total_calls if total_calls > 0 else 0.0
            )

            metrics["service_health_summary"][service_name] = {
                "status": service.status.value,
                "success_count": service.success_count,
                "error_count": service.error_count,
                "success_rate": round(success_rate, 3),
                "avg_response_time": round(service.response_time or 0.0, 3),
                "last_check": service.last_check,
                "fallback_active": service.fallback_active,
                "fallback_count": self.fallback_counts.get(service_name, 0),
            }

            # Circuit breaker status
            circuit_breaker = self.circuit_breakers.get(service_name)
            if circuit_breaker:
                metrics["circuit_breaker_status"][service_name] = {
                    "state": getattr(circuit_breaker, "state", "unknown"),
                    "failure_count": getattr(circuit_breaker, "failure_count", 0),
                    "success_count": getattr(circuit_breaker, "success_count", 0),
                    "last_failure_time": getattr(
                        circuit_breaker, "last_failure_time", None
                    ),
                }

        return metrics

    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time across all services."""
        response_times = [
            service.response_time
            for service in self.services.values()
            if service.response_time is not None
        ]
        return sum(response_times) / len(response_times) if response_times else 0.0

    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate across all services."""
        total_success = sum(service.success_count for service in self.services.values())
        total_calls = total_success + sum(
            service.error_count for service in self.services.values()
        )
        return total_success / total_calls if total_calls > 0 else 0.0

    def _get_circuit_breaker_status(self) -> Dict[str, str]:
        """Get circuit breaker status for all services."""
        return {
            name: getattr(breaker, "state", "unknown")
            for name, breaker in self.circuit_breakers.items()
        }

    def _initialize_default_services(self) -> None:
        """Initialize default service configurations."""

        # OpenAI service
        self.register_service(
            "openai",
            FallbackConfig(
                enabled=True,
                timeout=30.0,
                max_retries=3,
                fallback_message="AI service temporarily unavailable. Using cached responses when possible.",
                cache_fallback=True,
            ),
        )

        # Redis service
        self.register_service(
            "redis",
            FallbackConfig(
                enabled=True,
                timeout=5.0,
                max_retries=2,
                fallback_message="Caching service unavailable. Performance may be reduced.",
                cache_fallback=False,
                offline_mode=True,
            ),
        )

        # Vector store service
        self.register_service(
            "vector_store",
            FallbackConfig(
                enabled=True,
                timeout=10.0,
                max_retries=2,
                fallback_message="Search service degraded. Results may be limited.",
                cache_fallback=True,
            ),
        )

    def register_service(self, name: str, config: FallbackConfig) -> None:
        """
        Register a service for graceful degradation monitoring.

        Args:
            name: Service name
            config: Fallback configuration
        """
        self.services[name] = ServiceHealth(
            name=name,
            status=ServiceStatus.HEALTHY,
            last_check=time.time(),
            error_count=0,
            success_count=0,
        )

        self.fallback_configs[name] = config

        # Create circuit breaker
        self.circuit_breakers[name] = CircuitBreaker(
            name=f"{name}_degradation",
            config=CircuitBreakerConfig(
                failure_threshold=3, recovery_timeout=30.0, timeout=config.timeout
            ),
        )

        logger.info(f"Registered service '{name}' for graceful degradation")

    def register_fallback_handler(self, service_name: str, handler: Callable) -> None:
        """
        Register a fallback handler for a service.

        Args:
            service_name: Name of the service
            handler: Fallback handler function
        """
        self.fallback_handlers[service_name] = handler
        logger.info(f"Registered fallback handler for service '{service_name}'")

    async def execute_with_fallback(
        self,
        service_name: str,
        primary_func: Callable,
        *args,
        fallback_func: Optional[Callable] = None,
        cache=None,
        cache_key: Optional[str] = None,
        cache_ttl: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """
        Execute a function with graceful degradation fallback.

        Args:
            service_name: Name of the service
            primary_func: Primary function to execute
            *args: Function arguments
            fallback_func: Optional fallback function
            **kwargs: Function keyword arguments

        Returns:
            Function result or fallback result
        """
        service = self.services.get(service_name)
        if not service:
            logger.warning(
                f"Service '{service_name}' not registered for graceful degradation"
            )
            return await self._execute_function(primary_func, *args, **kwargs)

        config = self.fallback_configs[service_name]
        circuit_breaker = self.circuit_breakers[service_name]

        # Optional cache-first
        if cache and cache_key:
            try:
                cached = await cache.get(cache_key)
                if cached is not None:
                    logger.info("Cache-first hit", service=service_name)
                    return cached
            except Exception:
                pass

        try:
            # Try primary function with circuit breaker and timeout
            start_time = time.time()
            timeout_sec = self._get_timeout_for(
                service_name, float(getattr(config, "timeout", 5.0))
            )
            result = await asyncio.wait_for(
                circuit_breaker.call(primary_func, *args, **kwargs), timeout=timeout_sec
            )
            # Record success
            response_time = time.time() - start_time
            await self._record_success(service_name, response_time)
            # Populate cache on success
            if cache and cache_key:
                try:
                    ttl = int(cache_ttl or 0) or int(
                        getattr(settings, "cache_ttl", 300)
                    )
                    await cache.set(cache_key, result, ttl=ttl)
                except Exception:
                    pass
            return result

        except Exception as e:
            # Record failure
            await self._record_failure(service_name, e)
            self._inc_fallback(service_name)

            # Try fallback if available and enabled
            if config.enabled:
                # Execute fallback with the same timeout budget
                try:
                    timeout_sec = self._get_timeout_for(
                        service_name, float(getattr(config, "timeout", 5.0))
                    )
                    return await asyncio.wait_for(
                        self._execute_fallback(
                            service_name,
                            fallback_func or self.fallback_handlers.get(service_name),
                            e,
                            *args,
                            **kwargs,
                        ),
                        timeout=timeout_sec,
                    )
                except Exception as fb_err:
                    logger.error(
                        "Fallback execution failed",
                        service=service_name,
                        error=str(fb_err),
                    )
                    # If fallback fails too, return degraded response
                    return await self._degraded_response(service_name, e, fb_err)
            else:
                # No fallback, re-raise error
                raise

    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function (async or sync)."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    async def _execute_fallback(
        self,
        service_name: str,
        fallback_func: Optional[Callable],
        original_error: Exception,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute fallback logic for a failed service.

        Args:
            service_name: Name of the failed service
            fallback_func: Fallback function to execute
            original_error: Original error that triggered fallback
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Fallback result
        """
        service = self.services[service_name]
        config = self.fallback_configs[service_name]

        # Mark service as using fallback
        service.fallback_active = True

        logger.warning(
            f"Service '{service_name}' failed, executing fallback",
            error=str(original_error),
            fallback_message=config.fallback_message,
        )

        try:
            if fallback_func:
                # Execute custom fallback function
                result = await self._execute_function(fallback_func, *args, **kwargs)
                logger.info(
                    f"Fallback function executed successfully for service '{service_name}'"
                )
                return result
            else:
                # Default fallback behavior
                return await self._default_fallback(
                    service_name, original_error, *args, **kwargs
                )

        except Exception as fallback_error:
            logger.error(
                f"Fallback failed for service '{service_name}'",
                fallback_error=str(fallback_error),
                original_error=str(original_error),
            )

            # If fallback also fails, return degraded response
            return await self._degraded_response(
                service_name, original_error, fallback_error
            )

    async def _default_fallback(
        self, service_name: str, original_error: Exception, *args, **kwargs
    ) -> Any:
        """
        Default fallback behavior for services.

        Args:
            service_name: Name of the failed service
            original_error: Original error that triggered fallback
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Default fallback result
        """
        config = self.fallback_configs[service_name]
        lang = getattr(settings, "default_lang", "en")

        def _msg(en: str, fa: str) -> str:
            return fa if lang == "fa" else en

        if service_name == "openai":
            # For OpenAI, try to return cached response or generic message
            return await self._openai_fallback(original_error, *args, **kwargs)

        elif service_name == "redis":
            # For Redis, continue without caching
            logger.info(_msg("Continuing without Redis caching", "ادامه بدون کش ردیس"))
            return await self._redis_fallback(original_error, *args, **kwargs)

        elif service_name == "vector_store":
            # For vector store, return empty results or cached results
            res = await self._vector_store_fallback(original_error, *args, **kwargs)
            res["message"] = _msg(
                "Search service degraded. Results may be limited.",
                "سرویس جستجو دچار افت شده. نتایج محدود خواهد بود.",
            )
            return res

        else:
            # Generic fallback
            logger.warning(
                f"No specific fallback for service '{service_name}', using generic fallback"
            )
            return {
                "success": False,
                "error": str(original_error),
                "fallback_message": config.fallback_message
                or _msg("Service temporarily unavailable", "سرویس موقتاً در دسترس نیست"),
                "degraded": True,
            }

    async def _openai_fallback(self, error: Exception, *args, **kwargs) -> Any:
        """Fallback for OpenAI service failures."""
        # Try to return a cached response or generic message
        fallback_response = (
            "I apologize, but I'm experiencing technical difficulties with the AI service. "
            "Please try again in a few moments."
        )

        if settings.default_lang == "fa":
            fallback_response = (
                "متأسفانه در حال حاضر مشکل فنی در سرویس هوش مصنوعی وجود دارد. "
                "لطفاً چند لحظه دیگر دوباره تلاش کنید."
            )

        return {
            "answer": fallback_response,
            "sources": [],
            "confidence_score": 0.0,
            "processing_time": 0.0,
            "language": settings.default_lang,
            "degraded": True,
            "fallback_reason": str(error),
        }

    async def _redis_fallback(self, error: Exception, *args, **kwargs) -> Any:
        """Fallback for Redis service failures."""
        # Continue without caching
        logger.info("Continuing without Redis caching due to service failure")
        return None  # Indicates no cached data available

    async def _vector_store_fallback(self, error: Exception, *args, **kwargs) -> Any:
        """Fallback for vector store service failures."""
        # Return empty search results
        return {
            "chunks": [],
            "scores": [],
            "metadata": [],
            "degraded": True,
            "fallback_reason": str(error),
        }


    async def _degraded_response(
        self, service_name: str, original_error: Exception, fallback_error: Exception
    ) -> Any:
        """
        Generate a degraded response when both primary and fallback fail.

        Args:
            service_name: Name of the failed service
            original_error: Original error
            fallback_error: Fallback error

        Returns:
            Degraded response
        """
        config = self.fallback_configs[service_name]

        return {
            "success": False,
            "degraded": True,
            "service": service_name,
            "message": config.fallback_message
            or f"Service '{service_name}' is temporarily unavailable",
            "original_error": str(original_error),
            "fallback_error": str(fallback_error),
            "retry_suggested": True,
        }

    async def _record_success(self, service_name: str, response_time: float) -> None:
        """Record a successful service call."""
        service = self.services[service_name]
        service.success_count += 1
        service.response_time = response_time
        service.last_check = time.time()
        service.error_message = None
        service.fallback_active = False

        # Update status based on recent performance
        if service.error_count == 0:
            service.status = ServiceStatus.HEALTHY
        elif service.success_count > service.error_count * 2:
            service.status = ServiceStatus.DEGRADED

    async def _record_failure(self, service_name: str, error: Exception) -> None:
        """Record a failed service call."""
        # Check if service exists in services dict
        if service_name not in self.services:
            logger.warning(f"Service '{service_name}' not found in services registry")
            return

        service = self.services[service_name]
        service.error_count += 1
        service.last_check = time.time()
        service.error_message = str(error)

        # Update status based on error count
        if service.error_count >= 10:
            service.status = ServiceStatus.CRITICAL
        elif service.error_count >= 5:
            service.status = ServiceStatus.DEGRADED

        # Log error context
        # Build error context (can be used for external logging systems)
        _ = ErrorContext.from_exception(
            error,
            component="graceful_degradation",
            operation=f"service_{service_name}",
            service_name=service_name,
            error_count=service.error_count,
        )

        logger.error(
            f"Service '{service_name}' failure recorded",
            error_count=service.error_count,
            error_message=str(error),
        )

    def get_service_health(self, service_name: str) -> Optional[ServiceHealth]:
        """
        Get health information for a specific service.

        Args:
            service_name: Name of the service

        Returns:
            Service health information or None if not found
        """
        return self.services.get(service_name)

    def get_all_service_health(self) -> Dict[str, ServiceHealth]:
        """
        Get health information for all registered services.

        Returns:
            Dictionary mapping service names to health information
        """
        return self.services.copy()

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get overall system status based on service health.

        Returns:
            System status information
        """
        total_services = len(self.services)
        healthy_services = sum(
            1 for s in self.services.values() if s.status == ServiceStatus.HEALTHY
        )
        degraded_services = sum(
            1 for s in self.services.values() if s.status == ServiceStatus.DEGRADED
        )
        critical_services = sum(
            1 for s in self.services.values() if s.status == ServiceStatus.CRITICAL
        )
        offline_services = sum(
            1 for s in self.services.values() if s.status == ServiceStatus.OFFLINE
        )

        # Determine overall status
        if critical_services > 0 or offline_services > total_services // 2:
            overall_status = "critical"
        elif degraded_services > 0 or offline_services > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "overall_status": overall_status,
            "total_services": total_services,
            "healthy_services": healthy_services,
            "degraded_services": degraded_services,
            "critical_services": critical_services,
            "offline_services": offline_services,
            "services": {
                name: {
                    "status": service.status.value,
                    "error_count": service.error_count,
                    "success_count": service.success_count,
                    "fallback_active": service.fallback_active,
                    "last_check": service.last_check,
                }
                for name, service in self.services.items()
            },
        }

    async def reset_service_health(self, service_name: str) -> bool:
        """
        Reset health statistics for a service.

        Args:
            service_name: Name of the service

        Returns:
            True if successful, False if service not found
        """
        service = self.services.get(service_name)
        if not service:
            return False

        service.error_count = 0
        service.success_count = 0
        service.status = ServiceStatus.HEALTHY
        service.error_message = None
        service.fallback_active = False
        service.last_check = time.time()

        logger.info(f"Reset health statistics for service '{service_name}'")
        return True

    async def handle_component_failure(
        self,
        component_name: str,
        error: Exception,
        fallback_message: Optional[str] = None,
    ) -> None:
        """
        Handle component failure and record it in the graceful degradation system.

        Args:
            component_name: Name of the failed component
            error: The exception that occurred
            fallback_message: Optional fallback message to log
        """
        try:
            # Record the failure
            await self._record_failure(component_name, error)

            # Log the failure
            logger.error(
                f"Component '{component_name}' failed: {str(error)}",
                component=component_name,
                error_type=type(error).__name__,
            )

            # Log fallback message if provided
            if fallback_message:
                logger.warning(
                    f"Using fallback for '{component_name}': {fallback_message}"
                )

        except Exception as e:
            logger.error(
                f"Failed to handle component failure for '{component_name}': {e}"
            )

    def get_failed_components(self) -> List[str]:
        """
        Get list of components that have failed.

        Returns:
            List of component names that have failed
        """
        failed_components = []
        for name, service in self.services.items():
            if service.status in [
                ServiceStatus.DEGRADED,
                ServiceStatus.CRITICAL,
                ServiceStatus.OFFLINE,
            ]:
                failed_components.append(name)
        return failed_components


# Global graceful degradation service instance
graceful_degradation = GracefulDegradationService()
