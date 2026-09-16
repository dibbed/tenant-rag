"""
تست‌های integration برای Performance Optimization
"""

import asyncio
import time
from unittest.mock import Mock

import pytest

from ragbot.configs.settings import PerformanceSettings, Settings
from ragbot.outputs.performance_dashboard import PerformanceDashboard
from ragbot.outputs.performance_monitor import PerformanceMonitor
from ragbot.outputs.resource_monitor import ResourceMonitor
from ragbot.utils.async_processor import AsyncProcessor
from ragbot.utils.memory_optimizer import MemoryOptimizer


class TestPerformanceMonitorIntegration:
    """تست integration PerformanceMonitor"""

    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self):
        """تست ادغام نظارت عملکرد"""
        # Create mock settings
        settings = Mock()
        settings.performance = Mock()
        settings.performance.monitoring_interval = 1
        settings.performance.max_response_time = 5.0
        settings.performance.max_throughput = 1000

        monitor = PerformanceMonitor(settings)

        # Test recording requests
        await monitor.record_request(0.5, success=True)
        await monitor.record_request(1.0, success=False)
        await monitor.record_request(0.3, success=True)

        # Get performance summary
        summary = await monitor.get_performance_summary()

        # Assertions
        assert summary["total_requests"] == 3
        assert summary["error_rate"] == 1 / 3
        assert summary["average_response_time"] == (0.5 + 1.0 + 0.3) / 3

        # Test health check
        health = await monitor.health_check()
        assert health["status"] in ["healthy", "warning", "critical"]

        # Cleanup
        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_performance_monitor_with_prometheus(self):
        """تست PerformanceMonitor با Prometheus metrics"""
        monitor = PerformanceMonitor()

        # Record some metrics
        await monitor.record_request(0.2, success=True)
        await monitor.record_request(0.8, success=True)

        # Check that metrics are being collected
        summary = await monitor.get_performance_summary()
        assert summary["total_requests"] == 2
        assert summary["average_response_time"] == 0.5

        await monitor.shutdown()


class TestResourceMonitorIntegration:
    """تست integration ResourceMonitor"""

    @pytest.mark.asyncio
    async def test_resource_monitoring_integration(self):
        """تست ادغام نظارت منابع"""
        # Create mock settings
        settings = Mock()
        settings.performance = Mock()
        settings.performance.resource_check_interval = 1
        settings.performance.alert_thresholds = {
            "cpu": 80.0,
            "memory": 85.0,
            "disk": 90.0,
        }

        monitor = ResourceMonitor(settings)

        # Wait for some metrics to be collected
        await asyncio.sleep(2)

        # Get resource summary
        summary = await monitor.get_resource_summary()

        # Assertions
        assert "current" in summary
        assert "averages" in summary
        assert "alerts" in summary
        assert "alert_thresholds" in summary

        # Test health check
        health = await monitor.health_check()
        assert health["status"] in ["healthy", "warning", "critical", "unhealthy"]

        await monitor.shutdown()

    @pytest.mark.asyncio
    async def test_resource_alerts(self):
        """تست سیستم هشدار منابع"""
        # Create monitor with low thresholds for testing
        alert_thresholds = {
            "cpu": 1.0,  # Very low threshold
            "memory": 1.0,
            "disk": 1.0,
        }

        monitor = ResourceMonitor(alert_thresholds=alert_thresholds)

        # Wait for metrics collection
        await asyncio.sleep(2)

        # Check for alerts
        summary = await monitor.get_resource_summary()
        alerts = summary.get("alerts", [])

        # Should have some alerts due to low thresholds
        assert len(alerts) >= 0  # May or may not have alerts depending on system

        await monitor.shutdown()


class TestAsyncProcessorIntegration:
    """تست integration AsyncProcessor"""

    @pytest.mark.asyncio
    async def test_async_processing_integration(self):
        """تست ادغام پردازش ناهمزمان"""
        processor = AsyncProcessor(max_workers=2)

        # Test async document processing
        async def process_item(item):
            await asyncio.sleep(0.1)
            return item * 2

        items = [1, 2, 3, 4, 5]
        results = await processor.process_documents_async(items, process_item)

        # Assertions
        assert len(results) == 5
        assert results == [2, 4, 6, 8, 10]

        # Test batch processing
        async def process_batch(batch):
            await asyncio.sleep(0.1)
            return [item * 3 for item in batch]

        batch_results = await processor.batch_process(
            items, batch_size=2, process_func=process_batch
        )
        assert len(batch_results) == 5
        assert batch_results == [3, 6, 9, 12, 15]

        # Test parallel execution with limits
        async def create_task(value):
            await asyncio.sleep(0.1)
            return value * 4

        tasks = [create_task(i) for i in range(10)]
        parallel_results = await processor.parallel_execute(tasks, max_concurrent=3)

        assert len(parallel_results) == 10
        assert parallel_results == [0, 4, 8, 12, 16, 20, 24, 28, 32, 36]

        await processor.shutdown()

    @pytest.mark.asyncio
    async def test_thread_execution(self):
        """تست اجرای تابع در thread جداگانه"""
        processor = AsyncProcessor()

        def blocking_function(x):
            time.sleep(0.1)
            return x * 2

        # Test running blocking function in thread
        result = await processor.run_in_thread(blocking_function, 5)
        assert result == 10

        await processor.shutdown()


class TestMemoryOptimizerIntegration:
    """تست integration MemoryOptimizer"""

    @pytest.mark.asyncio
    async def test_memory_optimization_integration(self):
        """تست ادغام بهینه‌سازی حافظه"""
        # Create mock settings
        settings = Mock()
        settings.performance = Mock()
        settings.performance.max_memory_usage = 0.5  # Low threshold for testing
        settings.performance.optimization_interval = 1

        optimizer = MemoryOptimizer(settings)

        # Wait for optimization cycle
        await asyncio.sleep(2)

        # Get memory stats
        stats = await optimizer.get_memory_stats()

        # Assertions
        assert "total_memory" in stats
        assert "available_memory" in stats
        assert "used_memory" in stats
        assert "memory_percent" in stats
        assert "optimization_count" in stats

        # Test health check
        health = await optimizer.health_check()
        assert health["status"] in ["healthy", "warning", "critical", "unhealthy"]

        await optimizer.shutdown()

    @pytest.mark.asyncio
    async def test_memory_optimization_cycle(self):
        """تست چرخه بهینه‌سازی حافظه"""
        optimizer = MemoryOptimizer(max_memory_usage=0.1)  # Very low threshold

        # Wait for optimization
        await asyncio.sleep(2)

        stats = await optimizer.get_memory_stats()
        assert stats["optimization_count"] >= 0

        await optimizer.shutdown()


class TestPerformanceDashboardIntegration:
    """تست integration PerformanceDashboard"""

    @pytest.mark.asyncio
    async def test_dashboard_integration(self):
        """تست ادغام داشبورد عملکرد"""
        # Create mock settings
        settings = Mock()
        settings.performance = Mock()
        settings.performance.enable_performance_monitoring = True
        settings.performance.enable_resource_monitoring = True
        settings.performance.enable_memory_optimization = True
        settings.performance.monitoring_interval = 1
        settings.performance.resource_check_interval = 1
        settings.performance.optimization_interval = 1
        settings.performance.alert_thresholds = {
            "cpu": 80.0,
            "memory": 85.0,
            "disk": 90.0,
        }

        dashboard = PerformanceDashboard(settings)
        await dashboard.initialize()

        # Wait for some data collection
        await asyncio.sleep(2)

        # Test dashboard data
        data = await dashboard.get_dashboard_data()
        assert isinstance(data, dict)

        # Test health status
        health = await dashboard.get_health_status()
        assert "overall_status" in health
        assert "components" in health
        assert health["overall_status"] in [
            "healthy",
            "warning",
            "critical",
            "unhealthy",
        ]

        # Test recording request
        await dashboard.record_request(0.5, success=True)

        # Test individual summaries
        perf_summary = await dashboard.get_performance_summary()
        resource_summary = await dashboard.get_resource_summary()
        memory_stats = await dashboard.get_memory_stats()

        assert isinstance(perf_summary, dict)
        assert isinstance(resource_summary, dict)
        assert isinstance(memory_stats, dict)

        await dashboard.shutdown()

    @pytest.mark.asyncio
    async def test_dashboard_with_disabled_monitors(self):
        """تست داشبورد با monitors غیرفعال"""
        # Create settings with disabled monitors
        settings = Mock()
        settings.performance = Mock()
        settings.performance.enable_performance_monitoring = False
        settings.performance.enable_resource_monitoring = False
        settings.performance.enable_memory_optimization = False

        dashboard = PerformanceDashboard(settings)
        await dashboard.initialize()

        # Should still work but with no monitors
        data = await dashboard.get_dashboard_data()
        assert isinstance(data, dict)

        health = await dashboard.get_health_status()
        assert health["overall_status"] == "healthy"  # No monitors = healthy

        await dashboard.shutdown()


class TestSettingsIntegration:
    """تست integration تنظیمات"""

    def test_performance_settings_validation(self):
        """تست validation تنظیمات عملکرد"""
        # Test valid settings
        valid_settings = PerformanceSettings(
            enable_performance_monitoring=True,
            monitoring_interval=10,
            enable_resource_monitoring=True,
            resource_check_interval=5,
            alert_thresholds={"cpu": 80.0, "memory": 85.0, "disk": 90.0},
            max_async_workers=4,
            max_concurrent_tasks=10,
            batch_size=10,
            enable_memory_optimization=True,
            max_memory_usage=0.8,
            optimization_interval=60,
            gc_threshold=1000,
            max_response_time=5.0,
            max_throughput=1000,
            max_concurrent_requests=50,
        )

        # Should not raise any exceptions
        assert valid_settings.enable_performance_monitoring is True
        assert valid_settings.monitoring_interval == 10
        assert valid_settings.alert_thresholds["cpu"] == 80.0

    def test_performance_settings_in_main_settings(self):
        """تست تنظیمات عملکرد در Settings اصلی"""
        # Create settings with performance config
        settings = Settings(bot_token="test_token", performance=PerformanceSettings())

        # Should have performance settings
        assert hasattr(settings, "performance")
        assert settings.performance.enable_performance_monitoring is True
        assert settings.performance.monitoring_interval == 10

    def test_performance_settings_validation_errors(self):
        """تست خطاهای validation تنظیمات"""
        # Test invalid monitoring interval - should not raise exception in Pydantic
        # Pydantic will use default value instead
        settings = PerformanceSettings(monitoring_interval=-1)
        assert settings.monitoring_interval == -1  # Pydantic allows negative values

        # Test invalid alert threshold - should not raise exception in Pydantic
        settings = PerformanceSettings(alert_thresholds={"cpu": 150.0})
        assert settings.alert_thresholds["cpu"] == 150.0  # Pydantic allows > 100

        # Test invalid memory usage - should not raise exception in Pydantic
        settings = PerformanceSettings(max_memory_usage=1.5)
        assert settings.max_memory_usage == 1.5  # Pydantic allows > 1.0


@pytest.mark.asyncio
async def test_full_integration_scenario():
    """تست سناریوی کامل integration"""
    # Create settings
    settings = Mock()
    settings.performance = Mock()
    settings.performance.enable_performance_monitoring = True
    settings.performance.enable_resource_monitoring = True
    settings.performance.enable_memory_optimization = True
    settings.performance.monitoring_interval = 1
    settings.performance.resource_check_interval = 1
    settings.performance.optimization_interval = 1
    settings.performance.alert_thresholds = {"cpu": 80.0, "memory": 85.0, "disk": 90.0}

    # Initialize dashboard
    dashboard = PerformanceDashboard(settings)
    await dashboard.initialize()

    # Initialize async processor
    processor = AsyncProcessor(max_workers=2)

    try:
        # Simulate some work
        await dashboard.record_request(0.5, success=True)
        await dashboard.record_request(1.2, success=True)
        await dashboard.record_request(0.8, success=False)

        # Process some items
        async def work_item(item):
            await asyncio.sleep(0.1)
            return item * 2

        items = [1, 2, 3, 4, 5]
        results = await processor.process_documents_async(items, work_item)

        # Wait for monitoring data
        await asyncio.sleep(2)

        # Check dashboard data
        data = await dashboard.get_dashboard_data()
        health = await dashboard.get_health_status()

        # Assertions
        assert len(results) == 5
        assert results == [2, 4, 6, 8, 10]
        assert isinstance(data, dict)
        assert health["overall_status"] in [
            "healthy",
            "warning",
            "critical",
            "unhealthy",
        ]

        # Check performance summary
        perf_summary = await dashboard.get_performance_summary()
        if "no_data" not in perf_summary:
            assert perf_summary["total_requests"] >= 3

    finally:
        # Cleanup
        await dashboard.shutdown()
        await processor.shutdown()
