"""
Example: Run real-time monitoring components and print status.

Run:
    python -m examples.monitoring_example
"""

from __future__ import annotations

import asyncio

from ragbot.monitoring.health_checker import HealthChecker
from ragbot.monitoring.real_time_monitor import RealTimeMonitor


async def main() -> None:
    monitor = RealTimeMonitor(check_interval=1)
    checker = HealthChecker()
    checker.check_interval = 2

    await monitor.start_monitoring()
    # Run one round of health checks
    await checker._run_all_checks()  # for demo purposes

    # Let it collect a bit
    await asyncio.sleep(5)

    status = await monitor.get_current_status()
    health = await checker.get_health_status()
    history = await monitor.get_metrics_history(hours=1)

    print("Current status:", status, "\n")
    print("Health status:", health, "\n")
    print("Recent metrics count:", len(history), "\n")

    await monitor.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
