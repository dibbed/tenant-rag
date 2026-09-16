"""
Lightweight monitoring API adapters.

Persian developer notes:
- این فایل APIهای ساده‌ای را برای دریافت وضعیت سلامت و متریک‌ها فراهم می‌کند.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ragbot.monitoring.health_checker import HealthChecker
from ragbot.monitoring.real_time_monitor import RealTimeMonitor


class MonitoringAPI:
    """In-process API facade over monitoring components."""

    def __init__(self, monitor: RealTimeMonitor, checker: HealthChecker) -> None:
        self._monitor = monitor
        self._checker = checker

    async def get_status(self) -> Dict[str, Any]:
        return await self._monitor.get_current_status()

    async def get_metrics(self, hours: int = 24) -> List[Dict[str, Any]]:
        return await self._monitor.get_metrics_history(hours=hours)

    async def get_health(self) -> Dict[str, Any]:
        return await self._checker.get_health_status()
