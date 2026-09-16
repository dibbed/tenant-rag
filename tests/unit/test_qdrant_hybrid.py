import pytest


pytestmark = pytest.mark.asyncio


def _has_qdrant():
    try:
        import qdrant_client  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_qdrant(), reason="qdrant-client not installed")
async def test_qdrant_hybrid_search_local_path(tmp_path):
    from ragbot.rag.store.qdrant_store import QdrantVectorStore

    store = QdrantVectorStore(path=str(tmp_path / "qdrant"), collection_name="hybrid_test", embedding_dimension=4)

    texts = ["hello world", "qdrant hybrid store", "vector search"]
    embs = [[0.7, 0.1, 0.1, 0.0], [0.6, 0.1, 0.1, 0.0], [0.0, 0.1, 0.2, 0.3]]
    metas = [{"language": "en"}, {"language": "en"}, {"language": "en"}]
    await store.add_texts(texts, embeddings=embs, metadata=metas)

    q = [0.65, 0.1, 0.1, 0.0]
    res = await store.hybrid_search("hello hybrid", q, alpha=0.7, top_k=2)

    assert len(res.documents) >= 1
