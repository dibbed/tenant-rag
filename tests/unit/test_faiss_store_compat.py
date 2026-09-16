"""
Additional FAISSStore compatibility tests.

Covers:
- default/custom dimension wiring (dimension alias)
- awaitable behavior of query() when store is empty
"""

from pathlib import Path

import pytest

from ragbot.rag.store.faiss_store import FAISSStore


def test_dimension_alias_and_default(tmp_path: Path) -> None:
    # Default should be 1536
    s1 = FAISSStore(store_path=str(tmp_path / "s1"))
    assert s1.dimension == 1536

    # Legacy alias: dimension should override embedding_dimension
    s2 = FAISSStore(store_path=str(tmp_path / "s2"), dimension=1536)
    assert s2.dimension == 1536


@pytest.mark.asyncio
async def test_query_awaitable_empty_store(tmp_path: Path) -> None:
    store = FAISSStore(store_path=str(tmp_path / "empty"))
    # When index is empty, query should return an awaitable list (empty)
    res = await store.query([0.1] * 1536, top_k=3)
    assert isinstance(res, list)
    assert res == []

