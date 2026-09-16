"""
تست‌های CLI برای Performance Optimization
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ragbot.cli import cmd_performance


class TestCLIPerformance:
    """تست دستورات CLI مربوط به performance"""

    @pytest.mark.asyncio
    async def test_cmd_performance_success(self):
        """تست دستور performance با موفقیت"""
        # Create mock integration service
        mock_integration = Mock()

        # Mock performance summary
        mock_integration.get_performance_summary = AsyncMock(
            return_value={
                "average_response_time": 0.5,
                "total_requests": 100,
                "error_rate": 0.05,
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "active_connections": 12,
            }
        )

        # Mock resource summary
        mock_integration.get_resource_summary = AsyncMock(
            return_value={
                "current": {
                    "cpu_percent": 45.2,
                    "memory_percent": 67.8,
                    "disk_usage": 23.4,
                    "process_count": 156,
                },
                "averages": {"cpu_percent": 42.1, "memory_percent": 65.3},
                "alerts": [
                    {
                        "severity": "warning",
                        "message": "CPU usage is approaching threshold: 78.5%",
                        "timestamp": 1234567890,
                    }
                ],
                "alert_thresholds": {"cpu": 80.0, "memory": 85.0, "disk": 90.0},
            }
        )

        # Mock get_integration_service
        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            # Test the command
            result = await cmd_performance(Mock())

            # Should return 0 for success
            assert result == 0

    @pytest.mark.asyncio
    async def test_cmd_performance_no_data(self):
        """تست دستور performance بدون داده"""
        # Create mock integration service
        mock_integration = Mock()

        # Mock performance summary with no data
        mock_integration.get_performance_summary = AsyncMock(
            return_value={"no_data": True}
        )

        # Mock resource summary with no data
        mock_integration.get_resource_summary = AsyncMock(
            return_value={"no_data": True}
        )

        # Mock get_integration_service
        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            # Test the command
            result = await cmd_performance(Mock())

            # Should return 0 for success (no data is not an error)
            assert result == 0

    @pytest.mark.asyncio
    async def test_cmd_performance_performance_error(self):
        """تست دستور performance با خطا در performance summary"""
        # Create mock integration service
        mock_integration = Mock()

        # Mock performance summary with error
        mock_integration.get_performance_summary = AsyncMock(
            return_value={"error": "Performance monitoring failed"}
        )

        # Mock resource summary
        mock_integration.get_resource_summary = AsyncMock(
            return_value={
                "current": {
                    "cpu_percent": 45.2,
                    "memory_percent": 67.8,
                    "disk_usage": 23.4,
                    "process_count": 156,
                },
                "averages": {"cpu_percent": 42.1, "memory_percent": 65.3},
                "alerts": [],
                "alert_thresholds": {"cpu": 80.0, "memory": 85.0, "disk": 90.0},
            }
        )

        # Mock get_integration_service
        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            # Test the command
            result = await cmd_performance(Mock())

            # Should return 1 for error
            assert result == 1

    @pytest.mark.asyncio
    async def test_cmd_performance_resource_error(self):
        """تست دستور performance با خطا در resource summary"""
        # Create mock integration service
        mock_integration = Mock()

        # Mock performance summary
        mock_integration.get_performance_summary = AsyncMock(
            return_value={
                "average_response_time": 0.5,
                "total_requests": 100,
                "error_rate": 0.05,
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "active_connections": 12,
            }
        )

        # Mock resource summary with error
        mock_integration.get_resource_summary = AsyncMock(
            return_value={"error": "Resource monitoring failed"}
        )

        # Mock get_integration_service
        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            # Test the command
            result = await cmd_performance(Mock())

            # Should return 1 for error
            assert result == 1

    @pytest.mark.asyncio
    async def test_cmd_performance_with_alerts(self):
        """تست دستور performance با هشدارها"""
        # Create mock integration service
        mock_integration = Mock()

        # Mock performance summary
        mock_integration.get_performance_summary = AsyncMock(
            return_value={
                "average_response_time": 0.5,
                "total_requests": 100,
                "error_rate": 0.05,
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "active_connections": 12,
            }
        )

        # Mock resource summary with multiple alerts
        mock_integration.get_resource_summary = AsyncMock(
            return_value={
                "current": {
                    "cpu_percent": 85.2,
                    "memory_percent": 90.8,
                    "disk_usage": 95.4,
                    "process_count": 256,
                },
                "averages": {"cpu_percent": 82.1, "memory_percent": 88.3},
                "alerts": [
                    {
                        "severity": "critical",
                        "message": "Memory usage is high: 90.8%",
                        "timestamp": 1234567890,
                    },
                    {
                        "severity": "warning",
                        "message": "CPU usage is high: 85.2%",
                        "timestamp": 1234567891,
                    },
                    {
                        "severity": "warning",
                        "message": "Disk usage is high: 95.4%",
                        "timestamp": 1234567892,
                    },
                    {
                        "severity": "warning",
                        "message": "CPU usage is approaching threshold: 78.5%",
                        "timestamp": 1234567893,
                    },
                    {
                        "severity": "warning",
                        "message": "Memory usage is approaching threshold: 82.1%",
                        "timestamp": 1234567894,
                    },
                ],
                "alert_thresholds": {"cpu": 80.0, "memory": 85.0, "disk": 90.0},
            }
        )

        # Mock get_integration_service
        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            # Test the command
            result = await cmd_performance(Mock())

            # Should return 0 for success
            assert result == 0

    @pytest.mark.asyncio
    async def test_cmd_performance_exception_handling(self):
        """تست مدیریت exception در دستور performance"""
        # Create mock integration service that raises exception
        mock_integration = Mock()
        mock_integration.get_performance_summary = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        # Mock get_integration_service
        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            # Test the command
            result = await cmd_performance(Mock())

            # Should return 1 for error
            assert result == 1


class TestCLIPerformanceIntegration:
    """تست integration CLI با Performance Optimization"""

    @pytest.mark.asyncio
    async def test_cli_performance_command_exists(self):
        """تست وجود دستور performance در CLI"""
        from ragbot.cli import _build_parser

        parser = _build_parser()

        # Test that performance command exists
        args = parser.parse_args(["performance"])
        assert args.cmd == "performance"
        assert args.func == cmd_performance

    @pytest.mark.asyncio
    async def test_cli_performance_help(self):
        """تست help برای دستور performance"""
        from ragbot.cli import _build_parser

        parser = _build_parser()

        # Test help text
        help_text = parser.format_help()
        assert "performance" in help_text
        assert "Show performance metrics" in help_text

    @pytest.mark.asyncio
    async def test_cli_performance_with_real_integration(self):
        """تست CLI performance با integration واقعی"""
        # This test would require actual integration service
        # For now, we'll just test that the command can be called
        from ragbot.cli import _build_parser

        parser = _build_parser()

        # Parse performance command
        args = parser.parse_args(["performance"])

        # Should have the correct function
        assert args.func == cmd_performance

        # Should be callable
        assert callable(args.func)
