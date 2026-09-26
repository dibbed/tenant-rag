"""Phase 2 regression tests: tenant storage fails closed.

Audit findings C1, C2 and C12 (docs/BASELINE_AUDIT.md).

Vulnerability: when a tenant vector store could not be created or loaded,
RAGService.get_vector_store() returned the shared default store and
RAGService.get_retriever() returned the shared default retriever.
VectorStoreFactory.create_store() also fell back silently to a FAISS store
that ignores the tenant partition. A tenant request could then read from,
write to, or wipe a store that other tenants use. Tenant ids were used as
path segments without validation.

Expected behavior: a tenant storage failure raises TenantStorageError, no
operation touches the shared store or another tenant's store, the query API
returns HTTP 503, and invalid tenant ids are rejected.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ragbot.api.app import create_app
from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep
from ragbot.configs.settings import settings
from ragbot.rag.exceptions import (
    DocumentProcessingError,
    TenantStorageError,
    VectorStoreError,
)
from ragbot.rag.store.base import VectorDocument
from ragbot.rag.store.factory import VectorStoreFactory
from ragbot.services.rag_service import RAGService

SHARED_SECRET = "SHARED-DEFAULT-STORE-SECRET"
ALPHA_SECRET = "ALPHA-CONFIDENTIAL-QUARTERLY-FIGURES"
BETA_TEXT = "BETA-PUBLIC-BLOG-POST"
QUESTION = "What does the knowledge base say?"


class InMemoryStore:
    """Small async vector store that records how it is used."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.docs: List[VectorDocument] = []
        self.add_calls = 0
        self.clear_calls = 0

    async def add_texts(self, texts, embeddings, metadata=None):
        self.add_calls += 1
        metadata = metadata or [{} for _ in texts]
        ids = []
        for index, text in enumerate(texts):
            doc_id = f"{self.label}-{len(self.docs)}"
            self.docs.append(
                VectorDocument(
                    id=doc_id,
                    content=text,
                    embedding=list(embeddings[index]),
                    metadata=dict(metadata[index] or {}),
                )
            )
            ids.append(doc_id)
        return ids

    async def search(self, query_embedding, top_k=10, *args, **kwargs):
        return SimpleNamespace(documents=list(self.docs)[: int(top_k or 10)])

    async def clear(self):
        self.clear_calls += 1
        self.docs.clear()
        return True


class StoreScopedRetriever:
    """Stand-in for AdvancedRetriever that returns every document of its store."""

    def __init__(self, vector_store=None, embedder=None, **kwargs: Any) -> None:
        self.vector_store = vector_store
        self.calls = 0

    async def retrieve(self, question: str, top_k: int = 5, **kwargs: Any):
        self.calls += 1
        return list(self.vector_store.docs)


class HealthyFactory:
    """Stand-in for VectorStoreFactory.create_store: one store per partition."""

    def __init__(self) -> None:
        self.stores: Dict[str, InMemoryStore] = {}
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, store_type: str, allow_fallback: bool = True, **kwargs: Any):
        self.calls.append({"store_type": store_type, "allow_fallback": allow_fallback})
        key = str(kwargs.get("store_path") or kwargs.get("collection_name"))
        if key not in self.stores:
            self.stores[key] = InMemoryStore(key)
        return self.stores[key]


def broken_factory(store_type: str, allow_fallback: bool = True, **kwargs: Any):
    raise RuntimeError("tenant index file is corrupted")


class ExplodingRetriever:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("reranker model is missing")


@pytest.fixture
def shared_store() -> InMemoryStore:
    store = InMemoryStore("shared-default")
    store.docs.append(
        VectorDocument(
            id="shared-0",
            content=SHARED_SECRET,
            embedding=[0.1] * 8,
            metadata={"source": "shared.txt"},
        )
    )
    return store


@pytest.fixture
def tenant_env(monkeypatch, shared_store):
    """RAGService with a shared default store and multi-tenant mode enabled."""
    shared_retriever = StoreScopedRetriever(vector_store=shared_store)
    semantic_cache = MagicMock()
    semantic_cache.get_similar_answer = AsyncMock(return_value=None)
    semantic_cache.cache_answer = AsyncMock()
    semantic_cache.clear_cache = AsyncMock()
    embedder = MagicMock()
    embedder.embed_text = AsyncMock(return_value=[0.2] * 8)
    embedder.embed_query = AsyncMock(return_value=[0.2] * 8)
    embedder.embed_texts = AsyncMock(return_value=[[0.2] * 8])

    # Build the service in single-tenant mode so no tenant database is created.
    with patch.object(settings.multi_tenant, "enabled", False):
        service = RAGService(
            loaders={},
            chunker=MagicMock(),
            embedder=embedder,
            vector_store=shared_store,
            qa_chain=MagicMock(),
            advanced_retriever=shared_retriever,
            semantic_cache=semantic_cache,
        )
    # Echo the retrieved context as the answer, so any leaked chunk is visible.
    service._generate_answer = AsyncMock(
        side_effect=lambda context, question, lang: " | ".join(context)
    )
    monkeypatch.setattr(settings.multi_tenant, "enabled", True)
    monkeypatch.setattr(
        "ragbot.rag.retrieve.advanced_retriever.AdvancedRetriever", StoreScopedRetriever
    )
    return service, shared_store, shared_retriever


async def _ingest(service: RAGService, tenant_id: str, text: str) -> None:
    await service._store_chunks(
        [text],
        [[0.3] * 8],
        [{"source": f"{tenant_id}.txt", "tenant_id": tenant_id}],
        tenant_id=tenant_id,
    )


@pytest.mark.asyncio
async def test_tenant_b_query_never_returns_tenant_a_documents(tenant_env, monkeypatch):
    """Cross-tenant retrieval: each tenant sees only its own partition."""
    service, shared_store, shared_retriever = tenant_env
    factory = HealthyFactory()
    monkeypatch.setattr(VectorStoreFactory, "create_store", factory)

    await _ingest(service, "tenant_a", ALPHA_SECRET)
    await _ingest(service, "tenant_b", BETA_TEXT)

    result_b = await service.query_documents(QUESTION, tenant_id="tenant_b")
    assert BETA_TEXT in result_b.answer
    assert ALPHA_SECRET not in result_b.answer
    assert SHARED_SECRET not in result_b.answer

    result_a = await service.query_documents(QUESTION, tenant_id="tenant_a")
    assert ALPHA_SECRET in result_a.answer
    assert BETA_TEXT not in result_a.answer
    assert SHARED_SECRET not in result_a.answer

    store_a = service.get_vector_store("tenant_a")
    store_b = service.get_vector_store("tenant_b")
    assert store_a is not store_b
    assert shared_store is not store_a and shared_store is not store_b
    assert shared_retriever.calls == 0
    # C2: tenant stores are always created with the fallback disabled.
    assert factory.calls and all(call["allow_fallback"] is False for call in factory.calls)


@pytest.mark.asyncio
async def test_query_fails_closed_when_tenant_storage_cannot_be_loaded(tenant_env, monkeypatch):
    """C1 scenario: tenant A has data, its storage then breaks, and the query must
    fail with an explicit error instead of falling back to the shared store."""
    service, shared_store, shared_retriever = tenant_env
    monkeypatch.setattr(VectorStoreFactory, "create_store", HealthyFactory())

    # 1-2. Tenant A exists and has documents.
    await _ingest(service, "tenant_a", ALPHA_SECRET)
    healthy = await service.query_documents(QUESTION, tenant_id="tenant_a")
    assert ALPHA_SECRET in healthy.answer

    # 3. Tenant A storage breaks (for example a corrupted index after a restart).
    service._tenant_vector_stores.clear()
    service._tenant_retrievers.clear()
    monkeypatch.setattr(VectorStoreFactory, "create_store", broken_factory)

    # 4-5. The query fails safely: explicit error, no data, no fallback.
    with pytest.raises(TenantStorageError) as exc_info:
        await service.query_documents(QUESTION, tenant_id="tenant_a")
    assert exc_info.value.tenant_id == "tenant_a"
    assert shared_retriever.calls == 0
    assert "tenant_a" not in service._tenant_vector_stores
    assert [doc.content for doc in shared_store.docs] == [SHARED_SECRET]


@pytest.mark.asyncio
async def test_ingest_with_broken_tenant_storage_never_writes_to_shared_store(tenant_env, monkeypatch):
    """C1: ingestion for a tenant whose storage fails must not land in the shared index."""
    service, shared_store, _ = tenant_env
    monkeypatch.setattr(VectorStoreFactory, "create_store", broken_factory)

    with pytest.raises(DocumentProcessingError) as exc_info:
        await _ingest(service, "tenant_a", ALPHA_SECRET)

    assert isinstance(exc_info.value.__cause__, TenantStorageError)
    assert shared_store.add_calls == 0
    assert [doc.content for doc in shared_store.docs] == [SHARED_SECRET]


@pytest.mark.asyncio
async def test_reset_with_broken_tenant_storage_does_not_wipe_shared_store(tenant_env, monkeypatch):
    """C1: a tenant reset used to clear the shared store when the tenant store failed."""
    service, shared_store, _ = tenant_env
    monkeypatch.setattr(VectorStoreFactory, "create_store", broken_factory)

    assert await service.reset_store(tenant_id="tenant_a") is False
    assert shared_store.clear_calls == 0
    assert [doc.content for doc in shared_store.docs] == [SHARED_SECRET]


@pytest.mark.asyncio
async def test_tenant_retriever_failure_never_returns_shared_retriever(tenant_env, monkeypatch):
    """C1: if the tenant retriever cannot be built, the shared retriever is not used."""
    service, shared_store, shared_retriever = tenant_env
    monkeypatch.setattr(VectorStoreFactory, "create_store", HealthyFactory())
    monkeypatch.setattr(
        "ragbot.rag.retrieve.advanced_retriever.AdvancedRetriever", ExplodingRetriever
    )
    await _ingest(service, "tenant_a", ALPHA_SECRET)

    assert service.get_retriever("tenant_a") is None

    result = await service.query_documents(QUESTION, tenant_id="tenant_a")
    assert SHARED_SECRET not in result.answer
    assert shared_retriever.calls == 0


@pytest.mark.parametrize(
    "tenant_id",
    ["../tenant_b", "tenant_a/../../etc", "tenant a", ".hidden", "-dash-first", "a" * 65],
)
def test_tenant_id_path_traversal_is_rejected(tenant_env, monkeypatch, tenant_id):
    """C12: tenant ids are path segments; unsafe ids must never reach storage."""
    service, _, _ = tenant_env
    factory = HealthyFactory()
    monkeypatch.setattr(VectorStoreFactory, "create_store", factory)

    with pytest.raises(TenantStorageError):
        service.get_vector_store(tenant_id)
    assert factory.calls == []


@pytest.mark.parametrize(
    "tenant_id", ["tenant_a", "Acme01", "550e8400-e29b-41d4-a716-446655440000"]
)
def test_valid_tenant_ids_get_their_own_store(tenant_env, monkeypatch, tenant_id):
    service, shared_store, _ = tenant_env
    monkeypatch.setattr(VectorStoreFactory, "create_store", HealthyFactory())

    store = service.get_vector_store(tenant_id)
    assert store is not None and store is not shared_store


# --------------------------------------------------------------------------
# VectorStoreFactory strict mode (C2)
# --------------------------------------------------------------------------

FAKE_MODULE = "phase2_fake_vector_store_module"


class _BrokenStore:
    def __init__(self, **kwargs: Any) -> None:
        raise RuntimeError("cannot open tenant collection")


@pytest.fixture
def fallback_spy(monkeypatch):
    spy = MagicMock(name="fallback_store")
    monkeypatch.setattr(
        VectorStoreFactory,
        "_create_fallback_store",
        classmethod(lambda cls, **kwargs: spy(**kwargs)),
    )
    return spy


def _register(monkeypatch, name: str, module_path: str, dependencies: List[str]) -> None:
    monkeypatch.setitem(
        VectorStoreFactory._store_registry,
        name,
        {
            "class_name": "_BrokenStore",
            "module_path": module_path,
            "dependencies": dependencies,
            "capabilities": {},
            "description": "phase 2 test store",
            "best_for": "tests",
        },
    )


def test_factory_strict_mode_raises_when_dependencies_are_missing(monkeypatch, fallback_spy):
    _register(monkeypatch, "phase2missingdeps", FAKE_MODULE, ["phase2_missing_dependency_xyz"])
    with pytest.raises(VectorStoreError):
        VectorStoreFactory.create_store("phase2missingdeps", allow_fallback=False)
    fallback_spy.assert_not_called()


def test_factory_strict_mode_raises_when_import_fails(monkeypatch, fallback_spy):
    _register(monkeypatch, "phase2badimport", "phase2_missing_module_xyz", [])
    with pytest.raises(VectorStoreError):
        VectorStoreFactory.create_store("phase2badimport", allow_fallback=False)
    fallback_spy.assert_not_called()


def test_factory_strict_mode_raises_when_store_construction_fails(monkeypatch, fallback_spy):
    monkeypatch.setitem(sys.modules, FAKE_MODULE, SimpleNamespace(_BrokenStore=_BrokenStore))
    _register(monkeypatch, "phase2broken", FAKE_MODULE, [])
    with pytest.raises(VectorStoreError):
        VectorStoreFactory.create_store(
            "phase2broken", allow_fallback=False, collection_name="tenant_a"
        )
    fallback_spy.assert_not_called()


def test_factory_default_mode_keeps_legacy_fallback(monkeypatch, fallback_spy):
    """The non-tenant default store keeps the documented legacy fallback."""
    _register(monkeypatch, "phase2legacy", FAKE_MODULE, ["phase2_missing_dependency_xyz"])
    result = VectorStoreFactory.create_store("phase2legacy")
    fallback_spy.assert_called_once()
    assert result is fallback_spy.return_value


# --------------------------------------------------------------------------
# API layer
# --------------------------------------------------------------------------


def test_query_api_returns_503_when_tenant_storage_is_unavailable():
    """C1: the API reports tenant storage failures explicitly, without internals."""
    rag = MagicMock()
    rag.query_documents = AsyncMock(
        side_effect=TenantStorageError(
            "Vector store for tenant 'tenant_a' is unavailable",
            tenant_id="tenant_a",
            details="/srv/data/tenants/tenant_a/faiss.index is corrupted",
        )
    )
    integration = MagicMock()
    integration.track_user_action = AsyncMock()

    app = create_app(lifespan_context=None)
    app.dependency_overrides[get_integration_service_dep] = lambda: integration
    app.dependency_overrides[get_rag_service_dep] = lambda: rag
    with TestClient(app) as client:
        response = client.post("/api/v1/query", json={"question": QUESTION})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "Tenant storage is unavailable"
    assert "/srv/data" not in response.text
