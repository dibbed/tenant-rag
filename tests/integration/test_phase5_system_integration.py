#!/usr/bin/env python3
"""
Integration tests for Phase 5: System Performance & Resource Monitoring

Persian developer notes:
- تست‌های integration برای system performance monitoring
- شامل SystemPerformanceMonitor و SystemResourceMonitor
"""

import time
from unittest.mock import patch

from ragbot.outputs.metrics import SystemPerformanceMonitor
from ragbot.outputs.system_monitor import SystemResourceMonitor


class TestSystemPerformanceIntegration:
    """Integration tests for system performance monitoring."""

    def test_system_performance_monitor_integration(self):
        """Test SystemPerformanceMonitor integration."""
        monitor = SystemPerformanceMonitor()

        # Record various metrics
        monitor.record_cpu_usage(75.0)
        monitor.record_memory_usage(1024000000, 80.0)
        monitor.record_disk_usage(512000000000, 60.0)
        monitor.record_network_latency(0.05)
        monitor.record_response_time(2.0)
        monitor.record_request(success=True)
        monitor.record_request(success=False)
        monitor.update_concurrent_users(10)
        monitor.update_queue_length(5)

        # Get performance summary
        summary = monitor.get_performance_summary()

        assert "cpu_metrics" in summary
        assert "memory_metrics" in summary
        assert "disk_metrics" in summary
        assert "network_metrics" in summary
        assert "response_time_metrics" in summary
        assert "error_rate" in summary
        assert "throughput" in summary
        assert "concurrent_users" in summary
        assert "queue_length" in summary
        assert "bottlenecks" in summary

        # Verify specific values
        assert summary["concurrent_users"] == 10
        assert summary["queue_length"] == 5
        assert summary["total_requests"] == 2
        assert summary["total_errors"] == 1
        assert summary["error_rate"] == 50.0

    def test_system_performance_prometheus_integration(self):
        """Test system performance metrics Prometheus integration."""
        monitor = SystemPerformanceMonitor()

        # Record some test data
        for i in range(5):
            monitor.record_cpu_usage(70.0 + i * 5)
            monitor.record_memory_usage(1024000000 + i * 100000000, 80.0 + i * 2)
            monitor.record_disk_usage(512000000000 + i * 1000000000, 60.0 + i * 3)
            monitor.record_network_latency(0.05 + i * 0.01)
            monitor.record_response_time(2.0 + i * 0.5)
            monitor.record_request(success=i % 2 == 0)

        # Test metrics calculation
        summary = monitor.get_performance_summary()

        assert "cpu_metrics" in summary
        assert "memory_metrics" in summary
        assert "disk_metrics" in summary
        assert "network_metrics" in summary
        assert "response_time_metrics" in summary
        assert summary["total_requests"] == 5
        assert summary["total_errors"] == 2  # i % 2 == 0 for i=1,3

    def test_bottleneck_detection_integration(self):
        """Test bottleneck detection integration."""
        monitor = SystemPerformanceMonitor()

        # Test normal conditions
        monitor.record_cpu_usage(50.0)
        monitor.record_memory_usage(1024000000, 60.0)
        monitor.record_disk_usage(512000000000, 50.0)
        monitor.record_response_time(1.0)
        monitor.request_count = 100
        monitor.error_count = 2

        bottlenecks = monitor.detect_bottlenecks()
        assert len(bottlenecks) == 0

        # Test CPU bottleneck
        monitor.record_cpu_usage(95.0)
        bottlenecks = monitor.detect_bottlenecks()
        assert len(bottlenecks) > 0
        assert any("CPU usage" in bottleneck for bottleneck in bottlenecks)

        # Test memory bottleneck
        monitor.record_cpu_usage(50.0)
        monitor.record_memory_usage(1024000000, 96.0)
        bottlenecks = monitor.detect_bottlenecks()
        assert any("memory usage" in bottleneck for bottleneck in bottlenecks)

        # Test disk bottleneck
        monitor.record_memory_usage(1024000000, 60.0)
        monitor.record_disk_usage(512000000000, 96.0)
        bottlenecks = monitor.detect_bottlenecks()
        assert any("disk usage" in bottleneck for bottleneck in bottlenecks)

    def test_system_resource_monitor_integration(self):
        """Test SystemResourceMonitor integration."""
        monitor = SystemResourceMonitor()

        # Test system info collection
        system_info = monitor.get_system_info()
        assert "platform" in system_info
        assert "cpu_count" in system_info
        assert "total_memory" in system_info
        assert "total_disk" in system_info

        # Test metrics collection
        metrics = monitor.collect_metrics()
        assert "cpu_percent" in metrics
        assert "memory_bytes" in metrics
        assert "memory_percent" in metrics
        assert "disk_bytes" in metrics
        assert "disk_percent" in metrics
        assert "network_latency" in metrics
        assert "gpu_percent" in metrics
        assert "gpu_memory" in metrics
        assert "timestamp" in metrics

    def test_system_health_check_integration(self):
        """Test system health check integration."""
        monitor = SystemResourceMonitor()

        # Test health check
        health = monitor.check_health()

        assert "health_score" in health
        assert "status" in health
        assert "bottlenecks" in health
        assert "metrics" in health
        assert "timestamp" in health

        assert health["status"] in ["healthy", "warning", "critical"]
        assert 0 <= health["health_score"] <= 100

    def test_system_monitoring_lifecycle(self):
        """Test system monitoring lifecycle."""
        monitor = SystemResourceMonitor()

        # Test initial state
        assert not monitor.is_monitoring

        # Test start monitoring (mock to avoid blocking)
        with patch.object(monitor, "collect_metrics") as mock_collect:
            with patch.object(monitor, "record_metrics"):
                mock_collect.return_value = {
                    "cpu_percent": 50.0,
                    "memory_bytes": 1024000000,
                    "memory_percent": 60.0,
                    "disk_bytes": 512000000000,
                    "disk_percent": 50.0,
                    "network_latency": 0.05,
                    "gpu_percent": 0.0,
                    "gpu_memory": 0,
                    "timestamp": time.time(),
                }

                # Start monitoring in a separate thread
                import threading

                monitor_thread = threading.Thread(
                    target=monitor.start_monitoring,
                    args=(0.1,),  # Very short interval for testing
                )
                monitor_thread.daemon = True
                monitor_thread.start()

                # Wait a bit
                time.sleep(0.5)

                # Stop monitoring
                monitor.stop_monitoring()

                # Verify monitoring was active
                assert monitor.is_monitoring == False

    def test_system_performance_thresholds(self):
        """Test system performance thresholds."""
        monitor = SystemPerformanceMonitor()

        # Test thresholds are properly set
        thresholds = monitor.thresholds

        assert thresholds["cpu_warning"] == 70.0
        assert thresholds["cpu_critical"] == 90.0
        assert thresholds["memory_warning"] == 80.0
        assert thresholds["memory_critical"] == 95.0
        assert thresholds["disk_warning"] == 85.0
        assert thresholds["disk_critical"] == 95.0
        assert thresholds["response_time_warning"] == 5.0
        assert thresholds["response_time_critical"] == 10.0
        assert thresholds["error_rate_warning"] == 5.0
        assert thresholds["error_rate_critical"] == 10.0

    def test_system_metrics_persistence(self):
        """Test that system metrics persist across operations."""
        monitor = SystemPerformanceMonitor()

        # Record initial data
        monitor.record_cpu_usage(70.0)
        monitor.record_memory_usage(1024000000, 80.0)
        monitor.record_request(success=True)
        monitor.update_concurrent_users(5)

        # Verify data persistence
        assert len(monitor.cpu_history) == 1
        assert monitor.cpu_history[0] == 70.0
        assert len(monitor.memory_history) == 1
        assert monitor.memory_history[0] == 80.0
        assert monitor.request_count == 1
        assert monitor.error_count == 0
        assert monitor.concurrent_users == 5

        # Record additional data
        monitor.record_cpu_usage(80.0)
        monitor.record_memory_usage(2048000000, 85.0)
        monitor.record_request(success=False)
        monitor.update_concurrent_users(10)

        # Verify data accumulation
        assert len(monitor.cpu_history) == 2
        assert monitor.cpu_history[1] == 80.0
        assert len(monitor.memory_history) == 2
        assert monitor.memory_history[1] == 85.0
        assert monitor.request_count == 2
        assert monitor.error_count == 1
        assert monitor.concurrent_users == 10

        # Test summary includes both records
        summary = monitor.get_performance_summary()
        assert summary["total_requests"] == 2
        assert summary["total_errors"] == 1
        assert summary["concurrent_users"] == 10

    def test_system_performance_aggregation(self):
        """Test system performance metrics aggregation."""
        monitor = SystemPerformanceMonitor()

        # Record multiple measurements
        for i in range(10):
            monitor.record_cpu_usage(60.0 + i * 2)
            monitor.record_memory_usage(1024000000 + i * 100000000, 70.0 + i * 1)
            monitor.record_disk_usage(512000000000 + i * 50000000000, 60.0 + i * 2)
            monitor.record_network_latency(0.05 + i * 0.005)
            monitor.record_response_time(1.0 + i * 0.1)
            monitor.record_request(success=i % 3 != 0)

        # Test aggregation
        summary = monitor.get_performance_summary()

        assert summary["total_requests"] == 10
        assert summary["total_errors"] == 4  # i % 3 == 0 for i=0,3,6,9 (4 values)

        # Test metrics calculation
        cpu_metrics = summary["cpu_metrics"]
        assert cpu_metrics["min"] == 60.0
        assert cpu_metrics["max"] == 78.0
        assert abs(cpu_metrics["average"] - 69.0) < 0.001

        memory_metrics = summary["memory_metrics"]
        assert memory_metrics["min"] == 70.0
        assert memory_metrics["max"] == 79.0
        assert abs(memory_metrics["average"] - 74.5) < 0.001

    def test_system_performance_error_handling(self):
        """Test system performance error handling."""
        monitor = SystemPerformanceMonitor()

        # Test with invalid data
        monitor.record_cpu_usage(-10.0)  # Negative CPU
        monitor.record_memory_usage(-1000, 150.0)  # Negative memory, >100% usage
        monitor.record_disk_usage(-500000000, -10.0)  # Negative disk

        # Should handle gracefully
        cpu_metrics = monitor.get_cpu_metrics()
        assert cpu_metrics["current"] == -10.0  # Should record as-is

        memory_metrics = monitor.get_memory_metrics()
        assert memory_metrics["current"] == 150.0  # Should record as-is

        disk_metrics = monitor.get_disk_metrics()
        assert disk_metrics["current"] == -10.0  # Should record as-is

    def test_system_performance_edge_cases(self):
        """Test system performance edge cases."""
        monitor = SystemPerformanceMonitor()

        # Test with zero values
        monitor.record_cpu_usage(0.0)
        monitor.record_memory_usage(0, 0.0)
        monitor.record_disk_usage(0, 0.0)
        monitor.record_network_latency(0.0)
        monitor.record_response_time(0.0)

        # Test metrics calculation with zero values
        cpu_metrics = monitor.get_cpu_metrics()
        assert cpu_metrics["current"] == 0.0
        assert cpu_metrics["average"] == 0.0

        # Test throughput calculation with zero response time
        throughput = monitor.get_throughput()
        assert throughput == 0.0

        # Test error rate with zero requests
        error_rate = monitor.get_error_rate()
        assert error_rate == 0.0
