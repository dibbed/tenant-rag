"""
Optimization engine to orchestrate performance improvements.

This module coordinates the performance monitor, resource monitor,
asynchronous processing utilities, and memory optimizer to apply
runtime optimizations safely.
"""

import asyncio
from typing import Any, Optional

from loguru import logger

from ragbot.outputs.performance_monitor import PerformanceMonitor
from ragbot.outputs.resource_monitor import ResourceMonitor
from ragbot.utils.async_processor import AsyncProcessor
from ragbot.utils.memory_optimizer import MemoryOptimizer


class OptimizationEngine:
    """Orchestrates runtime performance optimizations."""

    def __init__(self, settings: Optional[Any] = None) -> None:
        """Initialize the optimization engine.

        Args:
            settings: Global settings object with performance config
        """
        self.settings = settings
        self.performance_monitor = PerformanceMonitor(settings=settings)
        self.resource_monitor = ResourceMonitor(settings=settings)
        self.async_processor = AsyncProcessor(
            max_workers=getattr(
                getattr(settings, "performance", None), "max_async_workers", 4
            )
        )
        self.memory_optimizer = MemoryOptimizer(settings=settings)

        self._engine_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the optimization engine loop."""
        if self._engine_task is not None:
            return

        async def _engine_loop() -> None:
            while True:
                try:
                    await self._run_optimization_cycle()
                    interval = 15
                    if self.settings and hasattr(self.settings, "performance"):
                        # Reuse monitoring interval to avoid extra knobs
                        interval = max(
                            5, int(self.settings.performance.monitoring_interval)
                        )
                    await asyncio.sleep(interval)
                except Exception as e:
                    logger.error(f"Optimization engine loop error: {e}")
                    await asyncio.sleep(15)

        self._engine_task = asyncio.create_task(_engine_loop())
        logger.info("Optimization engine started")

    async def _run_optimization_cycle(self) -> None:
        """Run a single optimization cycle based on current metrics."""
        perf = await self.performance_monitor.get_performance_summary()
        res = await self.resource_monitor.get_resource_summary()

        # Guard against missing data
        if not perf or not res or "error" in perf or "error" in res:
            return

        avg_rt = float(perf.get("average_response_time", 0.0))
        total_req = int(perf.get("total_requests", 0))
        err_rate = float(perf.get("error_rate", 0.0))
        mem_percent = float(res.get("current", {}).get("memory_percent", 0.0))
        cpu_percent = float(res.get("current", {}).get("cpu_percent", 0.0))

        # Thresholds from settings with sane defaults
        max_rt = 5.0
        if self.settings and hasattr(self.settings, "performance"):
            max_rt = float(getattr(self.settings.performance, "max_response_time", 5.0))

        # Heuristic actions
        actions = []

        # 1) If response time is high or error rate spikes, trigger light memory compaction
        if avg_rt > max_rt or err_rate > 0.2:
            await self.memory_optimizer._compact_memory()
            actions.append("compact_memory")

        # 2) If memory usage is high, run full memory optimization (includes GC and cache pruning hook)
        if mem_percent > 85.0:
            await self.memory_optimizer._optimize_memory()
            actions.append("optimize_memory")

        # 3) If CPU is hot, reduce async concurrency for the next period
        if cpu_percent > 85.0:
            try:
                # Reduce concurrency by 20% but keep >= 1
                current_workers = max(1, int(self.async_processor.max_workers * 0.8))
                if current_workers != self.async_processor.max_workers:
                    self.async_processor.max_workers = current_workers
                    actions.append(f"reduce_workers_to_{current_workers}")
            except Exception as e:
                logger.warning(f"Failed to adjust async workers: {e}")

        if actions:
            logger.info(
                "Optimization actions applied",
                avg_response_time=avg_rt,
                total_requests=total_req,
                error_rate=err_rate,
                memory_percent=mem_percent,
                cpu_percent=cpu_percent,
                actions=actions,
            )

    async def shutdown(self) -> None:
        """Shutdown the optimization engine and sub-components."""
        if self._engine_task:
            self._engine_task.cancel()
            try:
                await self._engine_task
            except asyncio.CancelledError:
                pass

        await self.performance_monitor.shutdown()
        await self.resource_monitor.shutdown()
        await self.memory_optimizer.shutdown()
        try:
            await self.async_processor.shutdown()
        except Exception:
            # Safe guard: older executors may have already been shutdown
            pass
