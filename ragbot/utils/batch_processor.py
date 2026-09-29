"""
Batch processing utilities optimized for throughput and memory usage.
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Any

from loguru import logger


async def process_in_batches(
    items: Sequence[Any],
    batch_size: int,
    handler: Callable[[list[Any]], Awaitable[list[Any]]],
) -> list[Any]:
    """Process items in batches using an async handler.

    Args:
        items: Items to process
        batch_size: Maximum batch size
        handler: Async function that accepts a list of items and returns list of results

    Returns:
        List of results from all batches in order
    """
    results: list[Any] = []
    try:
        for start in range(0, len(items), batch_size):
            batch = list(items[start : start + batch_size])
            batch_result = await handler(batch)
            if batch_result:
                results.extend(batch_result)
    except Exception as e:
        logger.error(f"Error processing batches: {e}")
    return results


async def map_concurrent(
    items: Iterable[Any],
    mapper: Callable[[Any], Awaitable[Any]],
    concurrency: int = 10,
) -> list[Any]:
    """Map items concurrently with semaphore-limited concurrency."""
    semaphore = asyncio.Semaphore(max(1, concurrency))
    results: list[Any] = []

    async def _run(item: Any) -> None:
        async with semaphore:
            try:
                result = await mapper(item)
                results.append(result)
            except Exception as e:
                logger.warning(f"map_concurrent item failed: {e}")

    await asyncio.gather(*[_run(item) for item in items])
    return results
