"""
تست‌های واحد برای ماژول نظارت بلادرنگ
"""

import asyncio

import pytest

from ragbot.monitoring.alert_manager import AlertManager, AlertRule
from ragbot.monitoring.health_checker import HealthChecker
from ragbot.monitoring.real_time_monitor import RealTimeMonitor, SystemMetrics


class TestRealTimeMonitor:
    @pytest.mark.asyncio
    async def test_monitoring_start_stop(self):
        monitor = RealTimeMonitor(check_interval=1)
        await monitor.start_monitoring()
        assert monitor.monitoring_active is True
        await asyncio.sleep(1.5)
        await monitor.stop_monitoring()
        assert monitor.monitoring_active is False

    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        monitor = RealTimeMonitor()
        metrics = await monitor._collect_system_metrics()  # internal OK for test
        assert isinstance(metrics, SystemMetrics)
        assert 0 <= metrics.cpu_usage <= 100
        assert 0 <= metrics.memory_usage <= 100
        assert 0 <= metrics.disk_usage <= 100
        assert metrics.response_time >= 0
        assert metrics.error_rate >= 0


class TestAlertManager:
    @pytest.mark.asyncio
    async def test_alert_rule_management(self):
        manager = AlertManager()
        rule = AlertRule("Test Rule", "cpu_usage > threshold", 90.0, "critical")
        await manager.add_alert_rule("test_rule", rule)
        assert "test_rule" in manager.alert_rules
        await manager.remove_alert_rule("test_rule")
        assert "test_rule" not in manager.alert_rules


class TestHealthChecker:
    @pytest.mark.asyncio
    async def test_health_checks(self):
        checker = HealthChecker()
        await checker._run_all_checks()  # internal OK for test
        assert len(checker.health_checks) > 0
        status = await checker.get_health_status()
        assert "overall_status" in status
        assert status["overall_status"] in ["healthy", "warning", "unhealthy"]
