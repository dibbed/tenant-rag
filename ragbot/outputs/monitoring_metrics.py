"""
Prometheus metrics facade for monitoring.

Persian developer notes:
- این لایه مستقل از سرویس اصلی، متریک‌های کلیدی را اکسپوز می‌کند.
"""

from __future__ import annotations

try:
    from prometheus_client import Gauge, Histogram
except Exception:  # Fallback stubs when prometheus_client missing

    class _Stub:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def set(self, *args, **kwargs) -> None:
            pass

        def observe(self, *args, **kwargs) -> None:
            pass

    Gauge = _Stub  # type: ignore
    Histogram = _Stub  # type: ignore


class MonitoringMetrics:
    """Facilitates updating and recording monitoring metrics."""

    def __init__(self) -> None:
        self.system_health = Gauge("rag_system_health", "System health score")
        self.response_time = Histogram(
            "rag_response_time_ms", "Response time in milliseconds"
        )
        self.error_rate = Gauge("rag_error_rate_percent", "Error rate percent")
        self.cpu_usage = Gauge("rag_cpu_usage_percent", "CPU usage percent")
        self.memory_usage = Gauge("rag_memory_usage_percent", "Memory usage percent")

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
