"""
End-to-end example to exercise performance optimization components.

Run:
  python -m examples.performance_optimization_example
"""

import asyncio
from time import perf_counter

from ragbot.services.integration_service import (
    get_integration_service,
    shutdown_integration_service,
)


async def main() -> None:
    svc = await get_integration_service()

    # Simulate several requests to record into performance monitor
    for i in range(5):
        t0 = perf_counter()
        # Here we could call RAG service; we simulate time cost
        await asyncio.sleep(0.02 + i * 0.005)
        dt = perf_counter() - t0
        await svc.record_request(dt, success=True)

    perf_summary = await svc.get_performance_summary()
    res_summary = await svc.get_resource_summary()
    health = await svc.health_check()

    print("Performance Summary:", perf_summary)
    print("Resource Summary:", res_summary)
    print("Health:", health)

    await shutdown_integration_service()


if __name__ == "__main__":
    asyncio.run(main())
