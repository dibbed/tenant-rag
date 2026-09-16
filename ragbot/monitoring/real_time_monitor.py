"""
Real-time system monitoring utilities.

Persian developer notes:
- این ماژول متریک‌های سیستم را به‌صورت دوره‌ای جمع‌آوری می‌کند، هشدارهای ساده ایجاد می‌کند،
  و وضعیت سلامت را برمی‌گرداند. کاملاً async، بدون بلاکینگ غیرضروری.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

import psutil


@dataclass
class SystemMetrics:
    """System metrics snapshot.

    Attributes:
        timestamp: Collection time.
        cpu_usage: CPU usage percent [0-100].
        memory_usage: Memory usage percent [0-100].
        disk_usage: Disk usage percent [0-100].
        network_io: Bytes sent/received.
        active_connections: Number of active connections.
        response_time: Simulated response time in milliseconds.
        error_rate: Simulated error rate percent.
    """

    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, int]
    active_connections: int
    response_time: float
    error_rate: float


@dataclass
class Alert:
    """Alert record."""

    id: str
    type: str
    severity: str
    message: str
    timestamp: datetime
    resolved: bool = False


class RealTimeMonitor:
    """Real-time monitor collecting metrics and emitting alerts."""

    def __init__(self, check_interval: int = 10) -> None:
        self.check_interval = check_interval
        self.metrics_history: List[SystemMetrics] = []
        self.active_alerts: List[Alert] = []
        self.monitoring_active = False

        self.alert_thresholds: Dict[str, float] = {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "disk_usage": 90.0,
            "response_time": 5.0,  # milliseconds threshold placeholder
            "error_rate": 10.0,
        }

        self._monitoring_task: asyncio.Task | None = None
        self._alert_check_task: asyncio.Task | None = None

    async def start_monitoring(self) -> None:
        """Start the monitoring background tasks."""
        if self.monitoring_active:
            return
        self.monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._alert_check_task = asyncio.create_task(self._alert_check_loop())
        print("✅ Real-time monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the monitoring background tasks."""
        self.monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._alert_check_task:
            self._alert_check_task.cancel()
        print("⏹️ Real-time monitoring stopped")

    async def _monitoring_loop(self) -> None:
        while self.monitoring_active:
            try:
                metrics = await self._collect_system_metrics()
                self.metrics_history.append(metrics)
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-500:]
                await asyncio.sleep(self.check_interval)
            except Exception as exc:
                print(f"❌ Error in monitoring loop: {exc}")
                await asyncio.sleep(self.check_interval)

    async def _alert_check_loop(self) -> None:
        while self.monitoring_active:
            try:
                await self._check_alerts()
                await asyncio.sleep(30)
            except Exception as exc:
                print(f"❌ Error in alert check loop: {exc}")
                await asyncio.sleep(30)

    async def _collect_system_metrics(self) -> SystemMetrics:
        now = datetime.now()
        cpu_usage = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        memory_usage = mem.percent
        disk = psutil.disk_usage("/")
        disk_usage = (disk.used / disk.total) * 100
        net = psutil.net_io_counters()
        network_io = {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv}
        connections = len(psutil.net_connections())
        response_time = await self._measure_response_time()
        error_rate = await self._calculate_error_rate()
        return SystemMetrics(
            timestamp=now,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            network_io=network_io,
            active_connections=connections,
            response_time=response_time,
            error_rate=error_rate,
        )

    async def _measure_response_time(self) -> float:
        start = time.time()
        await asyncio.sleep(0.01)
        end = time.time()
        return (end - start) * 1000.0

    async def _calculate_error_rate(self) -> float:
        return 2.5

    async def _check_alerts(self) -> None:
        if not self.metrics_history:
            return
        latest = self.metrics_history[-1]
        to_create: List[Dict[str, Any]] = []
        if latest.cpu_usage > self.alert_thresholds["cpu_usage"]:
            to_create.append(
                {
                    "type": "high_cpu",
                    "severity": "warning",
                    "message": f"CPU usage is high: {latest.cpu_usage:.1f}%",
                }
            )
        if latest.memory_usage > self.alert_thresholds["memory_usage"]:
            to_create.append(
                {
                    "type": "high_memory",
                    "severity": "critical",
                    "message": f"Memory usage is high: {latest.memory_usage:.1f}%",
                }
            )
        if latest.disk_usage > self.alert_thresholds["disk_usage"]:
            to_create.append(
                {
                    "type": "high_disk",
                    "severity": "warning",
                    "message": f"Disk usage is high: {latest.disk_usage:.1f}%",
                }
            )
        if latest.response_time > self.alert_thresholds["response_time"]:
            to_create.append(
                {
                    "type": "slow_response",
                    "severity": "warning",
                    "message": f"Response time is slow: {latest.response_time:.2f}ms",
                }
            )
        if latest.error_rate > self.alert_thresholds["error_rate"]:
            to_create.append(
                {
                    "type": "high_error_rate",
                    "severity": "critical",
                    "message": f"Error rate is high: {latest.error_rate:.1f}%",
                }
            )
        for data in to_create:
            await self._create_alert(data)

    async def _create_alert(self, alert_data: Dict[str, Any]) -> None:
        existing = None
        now = datetime.now()
        for alert in self.active_alerts:
            if (
                alert.type == alert_data["type"]
                and not alert.resolved
                and (now - alert.timestamp).total_seconds() < 300
            ):
                existing = alert
                break
        if existing:
            return
        alert = Alert(
            id=f"{alert_data['type']}_{int(time.time())}",
            type=alert_data["type"],
            severity=alert_data["severity"],
            message=alert_data["message"],
            timestamp=now,
        )
        self.active_alerts.append(alert)
        await self._send_alert(alert)

    async def _send_alert(self, alert: Alert) -> None:
        print(f"🚨 ALERT [{alert.severity.upper()}]: {alert.message}")

    async def get_current_status(self) -> Dict[str, Any]:
        if not self.metrics_history:
            return {"no_data": True}
        latest = self.metrics_history[-1]
        return {
            "timestamp": latest.timestamp.isoformat(),
            "system_health": await self._calculate_system_health(latest),
            "metrics": {
                "cpu_usage": latest.cpu_usage,
                "memory_usage": latest.memory_usage,
                "disk_usage": latest.disk_usage,
                "response_time": latest.response_time,
                "error_rate": latest.error_rate,
            },
            "active_alerts": len([a for a in self.active_alerts if not a.resolved]),
            "monitoring_active": self.monitoring_active,
        }

    async def _calculate_system_health(self, m: SystemMetrics) -> str:
        score = 100
        if m.cpu_usage > 80:
            score -= 20
        elif m.cpu_usage > 60:
            score -= 10
        if m.memory_usage > 85:
            score -= 25
        elif m.memory_usage > 70:
            score -= 15
        if m.disk_usage > 90:
            score -= 20
        elif m.disk_usage > 80:
            score -= 10
        if m.response_time > 5:
            score -= 15
        elif m.response_time > 2:
            score -= 5
        if m.error_rate > 10:
            score -= 20
        elif m.error_rate > 5:
            score -= 10
        if score >= 90:
            return "excellent"
        if score >= 70:
            return "good"
        if score >= 50:
            return "fair"
        if score >= 30:
            return "poor"
        return "critical"

    async def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "cpu_usage": m.cpu_usage,
                "memory_usage": m.memory_usage,
                "disk_usage": m.disk_usage,
                "response_time": m.response_time,
                "error_rate": m.error_rate,
            }
            for m in self.metrics_history
            if m.timestamp > cutoff
        ]

    async def resolve_alert(self, alert_id: str) -> None:
        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.resolved = True
                print(f"✅ Alert {alert_id} resolved")
                break
