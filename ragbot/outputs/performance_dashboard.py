"""
داشبورد عملکرد سیستم
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger

from ragbot.outputs.performance_monitor import PerformanceMonitor
from ragbot.outputs.resource_monitor import ResourceMonitor
from ragbot.utils.memory_optimizer import MemoryOptimizer

if TYPE_CHECKING:
    from ragbot.configs.settings import Settings


class PerformanceDashboard:
    """داشبورد عملکرد"""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize performance dashboard"""
        self.settings = settings
        self.monitors: dict[str, object] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all monitors"""
        try:
            if not self._initialized:
                # Initialize performance monitor
                if self.settings and self.settings.performance.enable_monitoring:
                    self.monitors["performance"] = PerformanceMonitor(self.settings)
                    logger.info("Performance monitor initialized")

                # Initialize resource monitor
                if (
                    self.settings
                    and self.settings.performance.enable_resource_monitoring
                ):
                    self.monitors["resource"] = ResourceMonitor(
                        self.settings, self.settings.performance.alert_thresholds
                    )
                    logger.info("Resource monitor initialized")

                # Initialize memory optimizer
                if (
                    self.settings
                    and self.settings.performance.enable_memory_optimization
                ):
                    self.monitors["memory"] = MemoryOptimizer(self.settings)
                    logger.info("Memory optimizer initialized")

                self._initialized = True
                logger.success("Performance dashboard initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing performance dashboard: {e}")
            raise

    async def get_dashboard_data(self) -> dict[str, Any]:
        """دریافت داده‌های داشبورد"""
        try:
            if not self._initialized:
                await self.initialize()

            data: dict[str, Any] = {}

            for name, monitor in self.monitors.items():
                try:
                    if hasattr(monitor, "get_performance_summary"):
                        data[name] = await monitor.get_performance_summary()
                    elif hasattr(monitor, "get_resource_summary"):
                        data[name] = await monitor.get_resource_summary()
                    elif hasattr(monitor, "get_memory_stats"):
                        data[name] = await monitor.get_memory_stats()
                except Exception as e:  # noqa: PERF203 - intentional per-iteration fault isolation
                    logger.error(f"Error getting data from {name} monitor: {e}")
                    data[name] = {"error": str(e)}

            return data
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {"error": str(e)}

    async def get_health_status(self) -> dict[str, Any]:
        """دریافت وضعیت سلامت سیستم"""
        try:
            if not self._initialized:
                await self.initialize()

            health_status: dict[str, Any] = {
                "overall_status": "healthy",
                "components": {},
                "timestamp": asyncio.get_event_loop().time(),
            }

            for name, monitor in self.monitors.items():
                try:
                    if hasattr(monitor, "health_check"):
                        component_health = await monitor.health_check()
                        health_status["components"][name] = component_health

                        # Update overall status based on component health
                        if component_health.get("status") == "critical":
                            health_status["overall_status"] = "critical"
                        elif (
                            component_health.get("status") == "unhealthy"
                            and health_status["overall_status"] == "healthy"
                        ):
                            health_status["overall_status"] = "degraded"
                        elif (
                            component_health.get("status") == "warning"
                            and health_status["overall_status"] == "healthy"
                        ):
                            health_status["overall_status"] = "warning"
                except Exception as e:  # noqa: PERF203 - intentional per-iteration fault isolation
                    logger.error(f"Error checking health of {name}: {e}")
                    health_status["components"][name] = {
                        "status": "unhealthy",
                        "error": str(e),
                    }
                    if health_status["overall_status"] == "healthy":
                        health_status["overall_status"] = "degraded"

            return health_status
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {"overall_status": "unhealthy", "error": str(e)}

    async def record_request(self, duration: float, success: bool = True) -> None:
        """ثبت درخواست در performance monitor"""
        try:
            monitor = self.monitors.get("performance")
            if isinstance(monitor, PerformanceMonitor):
                await monitor.record_request(duration, success)
        except Exception as e:
            logger.error(f"Error recording request: {e}")

    async def get_performance_summary(self) -> dict[str, Any]:
        """دریافت خلاصه عملکرد"""
        try:
            monitor = self.monitors.get("performance")
            if isinstance(monitor, PerformanceMonitor):
                return await monitor.get_performance_summary()
            return {"no_monitor": True}
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {"error": str(e)}

    async def get_resource_summary(self) -> dict[str, Any]:
        """دریافت خلاصه منابع"""
        try:
            monitor = self.monitors.get("resource")
            if isinstance(monitor, ResourceMonitor):
                return await monitor.get_resource_summary()
            return {"no_monitor": True}
        except Exception as e:
            logger.error(f"Error getting resource summary: {e}")
            return {"error": str(e)}

    async def get_memory_stats(self) -> dict[str, Any]:
        """دریافت آمار حافظه"""
        try:
            monitor = self.monitors.get("memory")
            if isinstance(monitor, MemoryOptimizer):
                return await monitor.get_memory_stats()
            return {"no_monitor": True}
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {"error": str(e)}

    async def shutdown(self) -> None:
        """خاموش کردن تمام monitors"""
        try:
            for name, monitor in self.monitors.items():
                try:
                    if hasattr(monitor, "shutdown"):
                        await monitor.shutdown()
                    logger.info(f"Monitor {name} shut down successfully")
                except Exception as e:  # noqa: PERF203 - intentional per-iteration fault isolation
                    logger.error(f"Error shutting down monitor {name}: {e}")

            self.monitors.clear()
            self._initialized = False
            logger.success("Performance dashboard shut down successfully")
        except Exception as e:
            logger.error(f"Error shutting down performance dashboard: {e}")


# Global dashboard instance
_dashboard: PerformanceDashboard | None = None


async def get_performance_dashboard(
    settings: Settings | None = None,
) -> PerformanceDashboard:
    """Get or create the global performance dashboard instance"""
    global _dashboard

    if _dashboard is None:
        _dashboard = PerformanceDashboard(settings)
        await _dashboard.initialize()

    return _dashboard


async def shutdown_performance_dashboard() -> None:
    """Shutdown the global performance dashboard"""
    global _dashboard

    if _dashboard is not None:
        await _dashboard.shutdown()
        _dashboard = None
