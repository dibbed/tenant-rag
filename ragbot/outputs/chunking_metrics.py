"""
Prometheus-style metrics placeholders for chunking (time, count, quality, size distribution).

This module avoids hard dependency on Prometheus client; you can later
wire real metrics. For now, it provides a minimal interface used by services/tests.
"""

from __future__ import annotations

from ragbot.outputs.logger import logger


class ChunkingMetrics:
    """Lightweight metrics recorder (logs-based)."""

    def record_chunking_time(self, duration: float) -> None:
        logger.info("Chunking time recorded", duration=round(duration, 4))

    def record_chunk_count(self, count: int) -> None:
        logger.info("Chunk count recorded", count=int(count))

    def update_chunk_quality(self, quality: float) -> None:
        logger.info("Chunk quality updated", quality=round(quality, 4))

    def record_chunk_size(self, size: int) -> None:
        logger.info("Chunk size observed", size=int(size))
