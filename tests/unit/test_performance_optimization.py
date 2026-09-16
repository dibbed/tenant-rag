import asyncio

import pytest

from ragbot.outputs.optimization_engine import OptimizationEngine
from ragbot.outputs.performance_monitor import PerformanceMonitor
from ragbot.outputs.resource_monitor import ResourceMonitor
from ragbot.utils.async_processor import AsyncProcessor
from ragbot.utils.memory_optimizer import MemoryOptimizer


@pytest.mark.asyncio
async def test_performance_monitor_basic_summary():
    monitor = PerformanceMonitor()
    # simulate a few requests
    await monitor.record_request(0.01, success=True)
    await monitor.record_request(0.02, success=False)
    summary = await monitor.get_performance_summary()
    assert "average_response_time" in summary
    assert summary["total_requests"] >= 2
    health = await monitor.health_check()
    assert health["status"] in {"healthy", "degraded"}
    await monitor.shutdown()


@pytest.mark.asyncio
async def test_resource_monitor_summary_and_alerts():
    monitor = ResourceMonitor()
    # Force one collection
    await monitor._collect_resource_metrics()
    summary = await monitor.get_resource_summary()
    assert "current" in summary
    assert "averages" in summary
    health = await monitor.health_check()
    assert health["status"] in {"healthy", "warning", "critical"}
    await monitor.shutdown()


@pytest.mark.asyncio
async def test_memory_optimizer_stats_and_health():
    optimizer = MemoryOptimizer()
    # trigger lightweight optimization path directly
    await optimizer._compact_memory()
    stats = await optimizer.get_memory_stats()
    assert "memory_percent" in stats
    health = await optimizer.health_check()
    assert set(health.keys()) >= {"status"}
    await optimizer.shutdown()


@pytest.mark.asyncio
async def test_async_processor_parallel_and_shutdown():
    processor = AsyncProcessor(max_workers=2)

    async def echo(x: int):
        await asyncio.sleep(0.01)
        return x * 2

    tasks = [echo(i) for i in range(5)]
    results = await processor.parallel_execute(tasks, max_concurrent=2)
    assert results == [i * 2 for i in range(5)]
    await processor.shutdown()


@pytest.mark.asyncio
async def test_optimization_engine_cycle_runs():
    engine = OptimizationEngine()
    # Run a single optimization cycle
    await engine._run_optimization_cycle()
    # Start and immediately shutdown to ensure lifecycle works
    await engine.start()
    await asyncio.sleep(0)
    await engine.shutdown()
