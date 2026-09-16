import pytest

from ragbot.rag.chunkers.adaptive_chunker import AdaptiveChunker
from ragbot.rag.chunkers.chunk_optimizer import ChunkOptimizer
from ragbot.rag.chunkers.hierarchical_chunker import HierarchicalChunker


@pytest.mark.asyncio
async def test_hierarchical_chunker_basic():
    txt = "# Title\n\n## Section 1\n\nThis is a long paragraph. It should be captured as level 3.\n\n## Section 2\n\nAnother long paragraph that exceeds minimal threshold to be considered."
    ch = HierarchicalChunker(min_chunk_chars=10, max_chunk_chars=2000)
    chunks = ch.chunk(txt)
    assert isinstance(chunks, list) and len(chunks) > 0
    # Ensure metadata present
    assert all("chunk_type" in c.metadata for c in chunks)
    assert any(c.metadata.get("level") == 1 for c in chunks) or any(
        c.metadata.get("structure_type") == "title" for c in chunks
    )


@pytest.mark.asyncio
async def test_adaptive_chunker_selects_strategy():
    text = (
        "This is a test document. It contains multiple sentences and some structure.\n\n"
        "## A Section\n\nParagraph content goes here."
    )
    ac = AdaptiveChunker()
    chunks = ac.chunk(text)
    assert isinstance(chunks, list) and len(chunks) > 0
    # Should produce TextChunk-compatible outputs
    assert all(hasattr(c, "content") and hasattr(c, "metadata") for c in chunks)


@pytest.mark.asyncio
async def test_chunk_optimizer_flow():
    # Create pseudo chunks
    from ragbot.rag.chunkers.base import TextChunk

    chunks = [
        TextChunk(content="short", metadata={}),
        TextChunk(content="A" * 1200, metadata={}),
        TextChunk(
            content="normal sized chunk with enough words to be valid", metadata={}
        ),
    ]
    opt = ChunkOptimizer(target_size=500, size_tolerance=0.2)
    optimized = await opt.optimize(chunks)
    assert isinstance(optimized, list) and len(optimized) > 0
    qa = await opt.analyze_quality(optimized)
    assert "quality_score" in qa and "total" in qa
