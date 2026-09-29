"""
Prometheus metrics facade for monitoring.

Persian developer notes:
- این لایه مستقل از سرویس اصلی، متریک‌های کلیدی را اکسپوز می‌کند.
"""

from __future__ import annotations

from typing import Protocol


class _GaugeLike(Protocol):
    def set(self, value: float) -> None: ...


class _HistogramLike(Protocol):
    def observe(self, value: float) -> None: ...


class _Stub:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def set(self, *args: object, **kwargs: object) -> None:
        pass

    def observe(self, *args: object, **kwargs: object) -> None:
        pass


def _create_gauge(name: str, description: str) -> _GaugeLike:
    try:
        from prometheus_client import Gauge
    except Exception:
        return _Stub()
    metric: _GaugeLike = Gauge(name, description)
    return metric


def _create_histogram(name: str, description: str) -> _HistogramLike:
    try:
        from prometheus_client import Histogram
    except Exception:
        return _Stub()
    metric: _HistogramLike = Histogram(name, description)
    return metric


class MonitoringMetrics:
    """Facilitates updating and recording monitoring metrics."""

    def __init__(self) -> None:
        self.system_health = _create_gauge("rag_system_health", "System health score")
        self.response_time = _create_histogram(
            "rag_response_time_ms", "Response time in milliseconds"
        )
        self.error_rate = _create_gauge("rag_error_rate_percent", "Error rate percent")
        self.cpu_usage = _create_gauge("rag_cpu_usage_percent", "CPU usage percent")
        self.memory_usage = _create_gauge(
            "rag_memory_usage_percent", "Memory usage percent"
        )

    def update_system_health(self, health_score: float) -> None:
        self.system_health.set(health_score)

    def record_response_time(self, duration_ms: float) -> None:
        self.response_time.observe(duration_ms)

    def update_error_rate(self, rate_percent: float) -> None:
        self.error_rate.set(rate_percent)

    def update_cpu_usage(self, usage_percent: float) -> None:
        self.cpu_usage.set(usage_percent)

    def update_memory_usage(self, usage_percent: float) -> None:
        self.memory_usage.set(usage_percent)
