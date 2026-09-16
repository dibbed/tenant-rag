"""
نظارت بر منابع سیستم
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict

import psutil
from loguru import logger


@dataclass
class ResourceUsage:
    """استفاده از منابع"""

    cpu_percent: float
    memory_percent: float
    disk_usage: float
    network_io: Dict[str, int]
    process_count: int


class ResourceMonitor:
    """نظارت بر منابع"""

    def __init__(self, settings=None, alert_thresholds: Dict[str, float] = None):
        """Initialize resource monitor"""
        self.settings = settings

        # تنظیمات هشدار
        if alert_thresholds:
            self.alert_thresholds = alert_thresholds
        else:
            # Support both typed settings object and dict fallback
            if (
                settings
                and hasattr(settings, "performance")
                and settings.performance is not None
            ):
                perf = settings.performance
                try:
                    # Pydantic settings object with attribute access
                    self.alert_thresholds = getattr(
                        perf,
                        "alert_thresholds",
                        {"cpu": 80.0, "memory": 85.0, "disk": 90.0},
                    )
                except Exception:
                    self.alert_thresholds = {"cpu": 80.0, "memory": 85.0, "disk": 90.0}
            else:
                self.alert_thresholds = {"cpu": 80.0, "memory": 85.0, "disk": 90.0}

        self.resource_history = []
        self.alerts = []

        # Background monitoring
        self._monitoring_task = None
        self._start_monitoring()

    def _start_monitoring(self):
        """شروع نظارت"""

        async def monitor_loop():
            while True:
                try:
                    await self._collect_resource_metrics()
                    if self.settings and hasattr(self.settings, "performance"):
                        interval = getattr(
                            self.settings.performance, "resource_check_interval", 5
                        )
                    else:
                        interval = 5
                    # Handle Mock objects
                    if hasattr(interval, "_mock_name"):
                        interval = 5
                    await asyncio.sleep(interval)
                except Exception as e:
                    logger.error(f"Error in resource monitoring loop: {e}")
                    await asyncio.sleep(5)

        self._monitoring_task = asyncio.create_task(monitor_loop())

    async def _collect_resource_metrics(self):
        """جمع‌آوری متریک‌های منابع"""
        try:
            current_time = time.time()

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100

            # Network I/O
            network_io = psutil.net_io_counters()

            # Process count
            process_count = len(psutil.pids())

            # ایجاد رکورد منابع
            resource_usage = ResourceUsage(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage=disk_percent,
                network_io={
                    "bytes_sent": network_io.bytes_sent,
                    "bytes_recv": network_io.bytes_recv,
                },
                process_count=process_count,
            )

            # اضافه کردن به تاریخچه
            self.resource_history.append(
                {"timestamp": current_time, "usage": resource_usage}
            )

            # محدود کردن تاریخچه
            if len(self.resource_history) > 1000:
                self.resource_history = self.resource_history[-500:]

            # بررسی هشدارها
            await self._check_alerts(resource_usage)
        except Exception as e:
            logger.error(f"Error collecting resource metrics: {e}")

    async def _check_alerts(self, usage: ResourceUsage):
        """بررسی هشدارها"""
        try:
            alerts = []

            # CPU alert
            if usage.cpu_percent > self.alert_thresholds["cpu"]:
                alerts.append(
                    {
                        "type": "high_cpu",
                        "severity": "warning",
                        "message": f"CPU usage is high: {usage.cpu_percent:.1f}%",
                        "timestamp": time.time(),
                    }
                )

            # Memory alert
            if usage.memory_percent > self.alert_thresholds["memory"]:
                alerts.append(
                    {
                        "type": "high_memory",
                        "severity": "critical",
                        "message": f"Memory usage is high: {usage.memory_percent:.1f}%",
                        "timestamp": time.time(),
                    }
                )

            # Disk alert
            if usage.disk_usage > self.alert_thresholds["disk"]:
                alerts.append(
                    {
                        "type": "high_disk",
                        "severity": "warning",
                        "message": f"Disk usage is high: {usage.disk_usage:.1f}%",
                        "timestamp": time.time(),
                    }
                )

            # اضافه کردن هشدارها
            self.alerts.extend(alerts)

            # محدود کردن هشدارها
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-50:]
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")

    async def get_resource_summary(self) -> Dict[str, Any]:
        """دریافت خلاصه منابع"""
        try:
            # اگر هنوز دیتایی جمع نشده، همین حالا یک نمونه جمع‌آوری کن
            if not self.resource_history:
                await self._collect_resource_metrics()
                if not self.resource_history:
                    return {"no_data": True}

            # آخرین استفاده از منابع
            latest_usage = self.resource_history[-1]["usage"]

            # محاسبه میانگین‌ها
            cpu_values = [
                entry["usage"].cpu_percent for entry in self.resource_history[-10:]
            ]
            memory_values = [
                entry["usage"].memory_percent for entry in self.resource_history[-10:]
            ]

            return {
                "current": {
                    "cpu_percent": latest_usage.cpu_percent,
                    "memory_percent": latest_usage.memory_percent,
                    "disk_usage": latest_usage.disk_usage,
                    "process_count": latest_usage.process_count,
                },
                "averages": {
                    "cpu_percent": sum(cpu_values) / len(cpu_values)
                    if cpu_values
                    else 0,
                    "memory_percent": sum(memory_values) / len(memory_values)
                    if memory_values
                    else 0,
                },
                "alerts": self.alerts[-10:],  # آخرین 10 هشدار
                "alert_thresholds": self.alert_thresholds,
            }
        except Exception as e:
            logger.error(f"Error getting resource summary: {e}")
            return {"error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """بررسی سلامت منابع"""
        try:
            summary = await self.get_resource_summary()

            if "error" in summary:
                return {"status": "unhealthy", "error": summary["error"]}

            # بررسی هشدارهای فعال
            critical_alerts = [
                alert
                for alert in summary.get("alerts", [])
                if alert.get("severity") == "critical"
            ]
            warning_alerts = [
                alert
                for alert in summary.get("alerts", [])
                if alert.get("severity") == "warning"
            ]

            if critical_alerts:
                return {
                    "status": "critical",
                    "reason": f"Critical alerts: {len(critical_alerts)}",
                    "alerts": critical_alerts,
                }
            elif warning_alerts:
                return {
                    "status": "warning",
                    "reason": f"Warning alerts: {len(warning_alerts)}",
                    "alerts": warning_alerts,
                }

            return {"status": "healthy", "metrics": summary}
        except Exception as e:
            logger.error(f"Error in resource health check: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def shutdown(self):
        """خاموش کردن نظارت"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
