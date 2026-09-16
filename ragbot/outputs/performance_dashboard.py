"""
داشبورد عملکرد سیستم
"""

import asyncio
from typing import Any, Dict, Optional

from loguru import logger

from ragbot.outputs.performance_monitor import PerformanceMonitor
from ragbot.outputs.resource_monitor import ResourceMonitor
from ragbot.utils.memory_optimizer import MemoryOptimizer


class PerformanceDashboard:
    """داشبورد عملکرد"""

    def __init__(self, settings=None):
        """Initialize performance dashboard"""
        self.settings = settings
        self.monitors = {}
        self._initialized = False

    async def initialize(self):
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

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """دریافت داده‌های داشبورد"""
        try:
            if not self._initialized:
                await self.initialize()

            data = {}

            for name, monitor in self.monitors.items():
                try:
                    if hasattr(monitor, "get_performance_summary"):
                        data[name] = await monitor.get_performance_summary()
                    elif hasattr(monitor, "get_resource_summary"):
                        data[name] = await monitor.get_resource_summary()
                    elif hasattr(monitor, "get_memory_stats"):
                        data[name] = await monitor.get_memory_stats()
                except Exception as e:
                    logger.error(f"Error getting data from {name} monitor: {e}")
                    data[name] = {"error": str(e)}

            return data
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {"error": str(e)}

    async def get_health_status(self) -> Dict[str, Any]:
        """دریافت وضعیت سلامت سیستم"""
        try:
            if not self._initialized:
                await self.initialize()

            health_status = {
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
                except Exception as e:
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

    async def record_request(self, duration: float, success: bool = True):
        """ثبت درخواست در performance monitor"""
        try:
            if "performance" in self.monitors:
                await self.monitors["performance"].record_request(duration, success)
        except Exception as e:
            logger.error(f"Error recording request: {e}")

    async def get_performance_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه عملکرد"""
        try:
            if "performance" in self.monitors:
                return await self.monitors["performance"].get_performance_summary()
            return {"no_monitor": True}
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {"error": str(e)}

    async def get_resource_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه منابع"""
        try:
            if "resource" in self.monitors:
                return await self.monitors["resource"].get_resource_summary()
            return {"no_monitor": True}
        except Exception as e:
            logger.error(f"Error getting resource summary: {e}")
            return {"error": str(e)}

    async def get_memory_stats(self) -> Dict[str, Any]:
        """دریافت آمار حافظه"""
        try:
            if "memory" in self.monitors:
                return await self.monitors["memory"].get_memory_stats()
            return {"no_monitor": True}
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {"error": str(e)}

    async def shutdown(self):
        """خاموش کردن تمام monitors"""
        try:
            for name, monitor in self.monitors.items():
                try:
                    if hasattr(monitor, "shutdown"):
                        await monitor.shutdown()
                    logger.info(f"Monitor {name} shut down successfully")
                except Exception as e:
                    logger.error(f"Error shutting down monitor {name}: {e}")

            self.monitors.clear()
            self._initialized = False
            logger.success("Performance dashboard shut down successfully")
        except Exception as e:
            logger.error(f"Error shutting down performance dashboard: {e}")


# Global dashboard instance
_dashboard: Optional[PerformanceDashboard] = None


async def get_performance_dashboard(settings=None) -> PerformanceDashboard:
    """Get or create the global performance dashboard instance"""
    global _dashboard

    if _dashboard is None:
        _dashboard = PerformanceDashboard(settings)
        await _dashboard.initialize()

    return _dashboard


async def shutdown_performance_dashboard():
    """Shutdown the global performance dashboard"""
    global _dashboard

    if _dashboard is not None:
        await _dashboard.shutdown()
        _dashboard = None
