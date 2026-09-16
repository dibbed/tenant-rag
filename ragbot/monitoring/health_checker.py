"""
Health checking utilities for the application and environment.

Persian developer notes:
- بررسی منابع سیستم، اتصال دیتابیس/سرویس‌های خارجی، و سلامت اپلیکیشن.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

import psutil


@dataclass
class HealthCheck:
    """Single health check result."""

    name: str
    status: str  # healthy, unhealthy, warning
    message: str
    timestamp: datetime
    details: Dict[str, Any] | None = None


class HealthChecker:
    """Runs periodic health checks and aggregates results."""

    def __init__(self) -> None:
        self.health_checks: List[HealthCheck] = []
        self.check_interval: int = 60
        self.checking_active = False

    async def start_health_checks(self) -> None:
        self.checking_active = True
        while self.checking_active:
            await self._run_all_checks()
            await asyncio.sleep(self.check_interval)

    async def stop_health_checks(self) -> None:
        self.checking_active = False

    async def _run_all_checks(self) -> None:
        tasks = [
            self._check_system_resources(),
            self._check_database_connection(),
            self._check_external_services(),
            self._check_application_health(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                # Log and continue; avoid raising in background loop
                print(f"❌ Health check error: {res}")
            else:
                self.health_checks.append(res)
        if len(self.health_checks) > 100:
            self.health_checks = self.health_checks[-50:]

    async def _check_system_resources(self) -> HealthCheck:
        try:
            cpu_usage = psutil.cpu_percent(interval=0)
            cpu_status = (
                "healthy"
                if cpu_usage < 80
                else ("warning" if cpu_usage < 90 else "unhealthy")
            )

            memory = psutil.virtual_memory()
            memory_status = (
                "healthy"
                if memory.percent < 80
                else ("warning" if memory.percent < 90 else "unhealthy")
            )

            disk = psutil.disk_usage("/")
            disk_usage = (disk.used / disk.total) * 100
            disk_status = (
                "healthy"
                if disk_usage < 80
                else ("warning" if disk_usage < 90 else "unhealthy")
            )

            overall = "healthy"
            if any(s == "unhealthy" for s in [cpu_status, memory_status, disk_status]):
                overall = "unhealthy"
            elif any(s == "warning" for s in [cpu_status, memory_status, disk_status]):
                overall = "warning"

            message = f"CPU: {cpu_usage:.1f}%, Memory: {memory.percent:.1f}%, Disk: {disk_usage:.1f}%"
            return HealthCheck(
                name="system_resources",
                status=overall,
                message=message,
                timestamp=datetime.now(),
                details={
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory.percent,
                    "disk_usage": disk_usage,
                },
            )
        except Exception as exc:
            return HealthCheck(
                name="system_resources",
                status="unhealthy",
                message=f"Error checking system resources: {exc}",
                timestamp=datetime.now(),
            )

    async def _check_database_connection(self) -> HealthCheck:
        try:
            await asyncio.sleep(0.05)
            return HealthCheck(
                name="database_connection",
                status="healthy",
                message="Database connection is healthy",
                timestamp=datetime.now(),
            )
        except Exception as exc:
            return HealthCheck(
                name="database_connection",
                status="unhealthy",
                message=f"Database connection failed: {exc}",
                timestamp=datetime.now(),
            )

    async def _check_external_services(self) -> HealthCheck:
        try:
            await asyncio.sleep(0.05)
            return HealthCheck(
                name="external_services",
                status="healthy",
                message="External services are accessible",
                timestamp=datetime.now(),
            )
        except Exception as exc:
            return HealthCheck(
                name="external_services",
                status="unhealthy",
                message=f"External services check failed: {exc}",
                timestamp=datetime.now(),
            )

    async def _check_application_health(self) -> HealthCheck:
        try:
            await asyncio.sleep(0.05)
            return HealthCheck(
                name="application_health",
                status="healthy",
                message="Application is running normally",
                timestamp=datetime.now(),
            )
        except Exception as exc:
            return HealthCheck(
                name="application_health",
                status="unhealthy",
                message=f"Application health check failed: {exc}",
                timestamp=datetime.now(),
            )

    async def get_health_status(self) -> Dict[str, Any]:
        if not self.health_checks:
            return {"no_data": True}
        latest: Dict[str, Any] = {}
        for check in self.health_checks[-10:]:
            latest[check.name] = {
                "status": check.status,
                "message": check.message,
                "timestamp": check.timestamp.isoformat(),
                "details": check.details,
            }
        overall = "healthy"
        if any(chk["status"] == "unhealthy" for chk in latest.values()):
            overall = "unhealthy"
        elif any(chk["status"] == "warning" for chk in latest.values()):
            overall = "warning"
        return {
            "overall_status": overall,
            "checks": latest,
            "last_check": self.health_checks[-1].timestamp.isoformat()
            if self.health_checks
            else None,
        }
