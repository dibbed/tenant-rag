import pytest


pytestmark = pytest.mark.asyncio

try:  # pragma: no cover - optional dependency
    import chromadb  # type: ignore  # noqa: F401

    CHROMA_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    CHROMA_AVAILABLE = False

try:  # pragma: no cover - optional dependency
    import qdrant_client  # type: ignore  # noqa: F401

    QDRANT_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    QDRANT_AVAILABLE = False


@pytest.mark.skipif(not CHROMA_AVAILABLE, reason="chromadb not installed")
async def test_chroma_store_ingest_and_search(tmp_path):
    from ragbot.rag.store.chroma_store import ChromaVectorStore

    store = ChromaVectorStore(
        persist_directory=str(tmp_path / "chroma_db"),
        collection_name="test_collection",
        embedding_dimension=4,
    )

    texts = ["سلام دنیا"]
    embeddings = [[0.1, 0.2, 0.3, 0.4]]
    metadata = [
        {
            "language": "fa",
            "page": 1,
            "span": {"start": 0, "end": 9},
            "source_type": "text",
        }
    ]

    await store.add_texts(texts, embeddings=embeddings, metadata=metadata)

    result = await store.search(
        embeddings[0],
        top_k=3,
        filters={"language": {"$eq": "fa"}, "page": {"$gte": 1}},
    )

    assert len(result.documents) == 1
    doc = result.documents[0]
    assert doc.metadata.get("language") == "fa"
    assert doc.metadata.get("page") == 1
    assert doc.metadata.get("span_start") == 0
    assert (doc.score or 0.0) > 0.9


@pytest.mark.skipif(not QDRANT_AVAILABLE, reason="qdrant-client not installed")
async def test_qdrant_store_ingest_and_search(tmp_path):
    from ragbot.rag.store.qdrant_store import QdrantVectorStore

    store = QdrantVectorStore(
        path=str(tmp_path / "qdrant_db"),
        collection_name="test_collection",
        embedding_dimension=4,
    )

    texts = ["hello world"]
    embeddings = [[0.5, 0.1, -0.2, 0.3]]
    metadata = [
        {
            "language": "en",
            "page": 2,
            "span": {"start": 0, "end": 11},
            "source_type": "text",
        }
    ]

    await store.add_texts(texts, embeddings=embeddings, metadata=metadata)

    result = await store.search(
        embeddings[0],
        top_k=3,
        filters={"language": {"$eq": "en"}, "page": {"$lte": 2}},
    )

    assert len(result.documents) == 1
    doc = result.documents[0]
    assert doc.metadata.get("language") == "en"
    assert doc.metadata.get("page") == 2
    assert doc.metadata.get("span_start") == 0
