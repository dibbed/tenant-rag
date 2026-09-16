#!/usr/bin/env python3
"""
System Resource Monitor for RAG System

Persian developer notes:
- این ماژول منابع سیستم را مانیتور می‌کند
- شامل CPU, Memory, Disk, Network, GPU monitoring
"""

import platform
import time
from typing import Any, Dict

import psutil

from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager, system_performance_monitor


class SystemResourceMonitor:
    """مانیتور منابع سیستم برای RAG system."""

    def __init__(self):
        """Initialize system resource monitor."""
        self.is_monitoring = False
        self.monitoring_thread = None
        self.last_cpu_times = None
        self.last_network_io = None

    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception as e:
            logger.warning(f"Failed to get CPU usage: {e}")
            return 0.0

    def get_memory_usage(self) -> tuple[int, float]:
        """Get memory usage in bytes and percentage."""
        try:
            memory = psutil.virtual_memory()
            return memory.used, memory.percent
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return 0, 0.0

    def get_disk_usage(self) -> tuple[int, float]:
        """Get disk usage in bytes and percentage."""
        try:
            disk = psutil.disk_usage("/")
            return disk.used, (disk.used / disk.total) * 100
        except Exception as e:
            logger.warning(f"Failed to get disk usage: {e}")
            return 0, 0.0

    def get_network_latency(self) -> float:
        """Get network latency (simplified ping)."""
        try:
            import subprocess

            if platform.system().lower() == "windows":
                result = subprocess.run(
                    ["ping", "-n", "1", "8.8.8.8"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            else:
                result = subprocess.run(
                    ["ping", "-c", "1", "8.8.8.8"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

            if result.returncode == 0:
                # Extract time from ping output (simplified)
                output = result.stdout
                if "time=" in output:
                    time_str = output.split("time=")[1].split()[0]
                    return (
                        float(time_str.replace("ms", "")) / 1000.0
                    )  # Convert to seconds
            return 0.1  # Default latency
        except Exception as e:
            logger.warning(f"Failed to get network latency: {e}")
            return 0.1

    def get_gpu_usage(self) -> tuple[float, int]:
        """Get GPU usage percentage and memory usage."""
        try:
            # Try to get GPU info using nvidia-ml-py if available
            try:
                import pynvml

                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)

                # Get GPU utilization
                gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_percent = gpu_util.gpu

                # Get GPU memory
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_memory = mem_info.used

                return gpu_percent, gpu_memory
            except ImportError:
                # Fallback: try nvidia-smi command
                import subprocess

                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu,memory.used",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    line = result.stdout.strip().split("\n")[0]
                    gpu_percent, gpu_memory = map(float, line.split(", "))
                    return gpu_percent, int(
                        gpu_memory * 1024 * 1024
                    )  # Convert MB to bytes
        except Exception as e:
            logger.warning(f"Failed to get GPU usage: {e}")

        return 0.0, 0

    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        try:
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "cpu_count": cpu_count,
                "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
                "total_memory": memory.total,
                "total_disk": disk.total,
                "boot_time": psutil.boot_time(),
            }
        except Exception as e:
            logger.warning(f"Failed to get system info: {e}")
            return {}

    def collect_metrics(self) -> Dict[str, Any]:
        """Collect all system metrics."""
        cpu_percent = self.get_cpu_usage()
        memory_bytes, memory_percent = self.get_memory_usage()
        disk_bytes, disk_percent = self.get_disk_usage()
        network_latency = self.get_network_latency()
        gpu_percent, gpu_memory = self.get_gpu_usage()

        return {
            "cpu_percent": cpu_percent,
            "memory_bytes": memory_bytes,
            "memory_percent": memory_percent,
            "disk_bytes": disk_bytes,
            "disk_percent": disk_percent,
            "network_latency": network_latency,
            "gpu_percent": gpu_percent,
            "gpu_memory": gpu_memory,
            "timestamp": time.time(),
        }

    def record_metrics(self, metrics: Dict[str, Any]) -> None:
        """Record metrics to performance monitor and Prometheus."""
        try:
            # Record to performance monitor
            system_performance_monitor.record_cpu_usage(metrics["cpu_percent"])
            system_performance_monitor.record_memory_usage(
                metrics["memory_bytes"], metrics["memory_percent"]
            )
            system_performance_monitor.record_disk_usage(
                metrics["disk_bytes"], metrics["disk_percent"]
            )
            system_performance_monitor.record_network_latency(
                metrics["network_latency"]
            )

            # Record to Prometheus
            system_performance_monitor.record_evaluation_metrics(
                metrics_manager, metrics
            )

            logger.debug(
                "System metrics recorded",
                cpu_percent=metrics["cpu_percent"],
                memory_percent=metrics["memory_percent"],
                disk_percent=metrics["disk_percent"],
                network_latency=metrics["network_latency"],
            )

        except Exception as e:
            logger.warning(f"Failed to record system metrics: {e}")

    def start_monitoring(self, interval: float = 30.0) -> None:
        """Start continuous system monitoring."""
        if self.is_monitoring:
            logger.warning("System monitoring is already running")
            return

        self.is_monitoring = True
        logger.info(f"Starting system monitoring with {interval}s interval")

        try:
            while self.is_monitoring:
                metrics = self.collect_metrics()
                self.record_metrics(metrics)
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("System monitoring stopped by user")
        except Exception as e:
            logger.error(f"System monitoring error: {e}")
        finally:
            self.is_monitoring = False

    def stop_monitoring(self) -> None:
        """Stop system monitoring."""
        self.is_monitoring = False
        logger.info("System monitoring stopped")

    def get_current_status(self) -> Dict[str, Any]:
        """Get current system status."""
        metrics = self.collect_metrics()
        performance_summary = system_performance_monitor.get_performance_summary()

        return {
            "current_metrics": metrics,
            "performance_summary": performance_summary,
            "system_info": self.get_system_info(),
            "is_monitoring": self.is_monitoring,
        }

    def check_health(self) -> Dict[str, Any]:
        """Check system health and return status."""
        metrics = self.collect_metrics()
        bottlenecks = system_performance_monitor.detect_bottlenecks()

        health_score = 100.0

        # Deduct points for high resource usage
        if metrics["cpu_percent"] > 90:
            health_score -= 30
        elif metrics["cpu_percent"] > 70:
            health_score -= 15

        if metrics["memory_percent"] > 95:
            health_score -= 30
        elif metrics["memory_percent"] > 80:
            health_score -= 15

        if metrics["disk_percent"] > 95:
            health_score -= 20
        elif metrics["disk_percent"] > 85:
            health_score -= 10

        if metrics["network_latency"] > 1.0:
            health_score -= 10
        elif metrics["network_latency"] > 0.5:
            health_score -= 5

        # Determine health status
        if health_score >= 90:
            status = "healthy"
        elif health_score >= 70:
            status = "warning"
        else:
            status = "critical"

        return {
            "health_score": max(0, health_score),
            "status": status,
            "bottlenecks": bottlenecks,
            "metrics": metrics,
            "timestamp": time.time(),
        }


# Global instance
system_resource_monitor = SystemResourceMonitor()
