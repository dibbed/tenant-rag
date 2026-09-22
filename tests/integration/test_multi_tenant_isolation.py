"""Integration tests verifying multi-tenant isolation invariants.

Invariants tested:
1. Semantic cache isolation: Tenant A cannot match or retrieve Tenant B's cached answers.
2. Vector store filesystem/partition isolation: Tenant A and Tenant B use isolated stores.
3. Tenant-scoped reset: Resetting Tenant A does not wipe or affect Tenant B's store or cache.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from ragbot.caching.semantic_cache import SemanticCache
from ragbot.configs.settings import Settings, MultiTenantSettings
from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.faiss_store import FAISSStore
from ragbot.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_semantic_cache_tenant_isolation(tmp_path: Path):
    """Verify that semantic cache strictly isolates entries between different tenants."""
    cache_settings = Settings(
        cache_dir=tmp_path / "cache",
        multi_tenant=MultiTenantSettings(enabled=True),
    )

    mock_embedder = MagicMock()
    mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 384)
    mock_embedder.embed_texts = AsyncMock(return_value=[[0.1] * 384])
    cache = SemanticCache(similarity_threshold=0.8, embedder=mock_embedder)

    # 1. Tenant Alpha caches an answer
    query = "What is the secret deployment protocol?"
    await cache.cache_answer(
        query=query,
        answer="Alpha-Confidential-Response",
        context=["alpha_handbook.pdf"],
        metadata={"tenant_id": "tenant_alpha"},
        tenant_id="tenant_alpha",
    )

    # 2. Tenant Beta queries the exact same question
    beta_result = await cache.get_similar_answer(
        query=query,
        tenant_id="tenant_beta",
    )
    # Tenant Beta MUST NOT see Tenant Alpha's cached answer!
    assert beta_result is None

    # 3. Tenant Alpha queries the exact same question
    alpha_result = await cache.get_similar_answer(
        query=query,
        tenant_id="tenant_alpha",
    )
    assert alpha_result is not None
    assert alpha_result.answer == "Alpha-Confidential-Response"

    # 4. Tenant Beta caches its own distinct answer
    await cache.cache_answer(
        query=query,
        answer="Beta-Public-Response",
        context=["beta_handbook.pdf"],
        metadata={"tenant_id": "tenant_beta"},
        tenant_id="tenant_beta",
    )

    beta_cached = await cache.get_similar_answer(
        query=query,
        tenant_id="tenant_beta",
    )
    assert beta_cached is not None
    assert beta_cached.answer == "Beta-Public-Response"

    # 5. Clear only Tenant Alpha's cache
    await cache.clear_cache(tenant_id="tenant_alpha")

    # Alpha's answer is gone
    assert await cache.get_similar_answer(query=query, tenant_id="tenant_alpha") is None

    # Beta's answer remains intact
    beta_still_cached = await cache.get_similar_answer(query=query, tenant_id="tenant_beta")
    assert beta_still_cached is not None
    assert beta_still_cached.answer == "Beta-Public-Response"


@pytest.mark.asyncio
async def test_faiss_vector_store_filesystem_isolation(tmp_path: Path):
    """Verify that FAISS vector stores use isolated tenant subdirectories."""
    store_base = tmp_path / "faiss_stores"

    # Instantiate two separate FAISS stores simulating RAGService get_vector_store
    alpha_dir = store_base / "tenants" / "tenant_alpha"
    beta_dir = store_base / "tenants" / "tenant_beta"

    store_alpha = FAISSStore(store_path=str(alpha_dir), dimension=128)
    store_beta = FAISSStore(store_path=str(beta_dir), dimension=128)

    # Add document to Tenant Alpha
    doc_alpha = VectorDocument(
        id="alpha_doc_1",
        content="Alpha confidential quarterly financials",
        embedding=[0.5] * 128,
        metadata={"tenant_id": "tenant_alpha", "sensitivity": "high"},
    )
    await store_alpha.add_documents([doc_alpha])
    await store_alpha.save()

    # Add document to Tenant Beta
    doc_beta = VectorDocument(
        id="beta_doc_1",
        content="Beta marketing public blog post",
        embedding=[0.5] * 128,
        metadata={"tenant_id": "tenant_beta", "sensitivity": "low"},
    )
    await store_beta.add_documents([doc_beta])
    await store_beta.save()

    # Query Tenant Alpha store
    results_alpha = await store_alpha.search([0.5] * 128, k=5)
    contents_alpha = [r.content for r in results_alpha.documents]
    assert "Alpha confidential quarterly financials" in contents_alpha
    assert "Beta marketing public blog post" not in contents_alpha

    # Query Tenant Beta store
    results_beta = await store_beta.search([0.5] * 128, k=5)
    contents_beta = [r.content for r in results_beta.documents]
    assert "Beta marketing public blog post" in contents_beta
    assert "Alpha confidential quarterly financials" not in contents_beta

    # Verify separate directory structures exist on disk
    assert alpha_dir.exists()
    assert beta_dir.exists()
    assert alpha_dir != beta_dir


@pytest.mark.asyncio
async def test_rag_service_tenant_reset_isolation(tmp_path: Path):
    """Verify that resetting a tenant's store in RAGService does not affect other tenants."""
    mock_cache = MagicMock()
    mock_cache.clear_cache = AsyncMock()

    service = RAGService(
        loaders={},
        chunker=MagicMock(),
        embedder=MagicMock(),
        vector_store=MagicMock(),
        qa_chain=MagicMock(),
        semantic_cache=mock_cache,
    )

    # Mock tenant stores
    mock_store_alpha = MagicMock()
    mock_store_alpha.clear = AsyncMock(return_value=True)
    mock_store_beta = MagicMock()
    mock_store_beta.clear = AsyncMock(return_value=True)

    service._tenant_vector_stores["tenant_alpha"] = mock_store_alpha
    service._tenant_vector_stores["tenant_beta"] = mock_store_beta

    # Reset Tenant Alpha
    reset_result = await service.reset_store(tenant_id="tenant_alpha")
    assert reset_result is True

    # Tenant Alpha store was cleared
    mock_store_alpha.clear.assert_called_once()
    # Tenant Beta store was NOT cleared
    mock_store_beta.clear.assert_not_called()
    # Tenant Alpha cache was cleared with tenant_id="tenant_alpha"
    mock_cache.clear_cache.assert_called_once_with(tenant_id="tenant_alpha")
