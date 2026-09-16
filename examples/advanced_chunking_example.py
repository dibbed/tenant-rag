#!/usr/bin/env python3
"""
Advanced Chunking Example

- Loads a sample Persian/English mixed text
- Runs AdaptiveChunker to choose best strategy (semantic/hierarchical/hybrid/token)
- Prints chunk summary and a few sample chunks
"""

from __future__ import annotations

import asyncio
import textwrap

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag import AdaptiveChunker, ChunkOptimizer

SAMPLE_TEXT = textwrap.dedent(
    """
    # راهنمای پروژه RAG Telegram Assistant

    این پروژه یک بات تلگرام با معماری RAG است که برای بازیابی و پاسخ‌دهی مبتنی بر اسناد طراحی شده.
    ساختار کلان شامل بخش‌های زیر است:
    - Vector Store مبتنی بر FAISS
    - Embedding با Sentence Transformers (intfloat/e5-small-v2)
    - LLM از طریق OpenRouter (x-ai/grok-4-fast:free)

    ## Chunking
    هدف chunking ایجاد قطعات معنایی منسجم با اندازه بهینه برای بهبود retrieval است. پارامترها:
    - اندازه هدف: ۵۰۰ کاراکتر تقریبی
    - هم‌پوشانی پویا در مرزها
    - پشتیبانی از فارسی/انگلیسی

    This section is in English to test sentence splitting and semantic grouping.
    We want chunks to preserve meaning while staying within token limits.
    The adaptive strategy should pick a reasonable approach based on structure and length.
    """
).strip()


async def main() -> None:
    logger.info("Running Advanced Chunking Example")
    logger.info(
        "Chunking strategy",
        strategy=getattr(settings.advanced_chunking, "chunking_strategy", "semantic"),
    )

    chunker = AdaptiveChunker()
    optimizer = ChunkOptimizer(
        target_size=getattr(settings.advanced_chunking, "chunk_target_size", 500),
        size_tolerance=getattr(settings.advanced_chunking, "chunk_size_tolerance", 0.2),
    )

    # Produce TextChunks
    chunks = chunker.chunk(SAMPLE_TEXT)
    logger.info("Chunks created", count=len(chunks))

    # Optimize sizes
    optimized = await optimizer.optimize(chunks)
    qa = await optimizer.analyze_quality(optimized)

    # Print summary
    print("\n===== Advanced Chunking Summary =====")
    print(
        f"Strategy: {getattr(settings.advanced_chunking, 'chunking_strategy', 'semantic')}"
    )
    print(f"Chunks: {len(chunks)} -> Optimized: {len(optimized)}")
    print("Quality:", qa)

    # Show a few chunks
    preview_count = min(3, len(optimized))
    for i in range(preview_count):
        c = optimized[i]
        meta_type = c.metadata.get("chunk_type", "n/a")
        level = c.metadata.get("level")
        print("\n--- Chunk", i, f"type={meta_type}", f"level={level}")
        print(c.content[:300] + ("..." if len(c.content) > 300 else ""))


if __name__ == "__main__":
    asyncio.run(main())
