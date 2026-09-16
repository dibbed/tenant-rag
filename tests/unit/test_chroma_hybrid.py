import pytest


pytestmark = pytest.mark.asyncio


def _has_chromadb():
    try:
        import chromadb  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_chromadb(), reason="chromadb not installed")
async def test_chroma_hybrid_search_returns_results(tmp_path):
    from ragbot.rag.store.chroma_store import ChromaVectorStore

    store = ChromaVectorStore(
        persist_directory=str(tmp_path / "chroma_db"),
        collection_name="hybrid_test",
        embedding_dimension=4,
    )

    texts = ["hello world", "another doc", "world of hybrid"]
    embs = [
        [0.7, 0.1, 0.2, 0.0],
        [0.0, 0.1, 0.1, 0.0],
        [0.6, 0.1, 0.2, 0.0],
    ]
    metas = [
        {"language": "en", "page": 1, "span": {"start": 0, "end": 11}},
        {"language": "en", "page": 2, "span": {"start": 0, "end": 11}},
        {"language": "en", "page": 3, "span": {"start": 0, "end": 15}},
    ]

    await store.add_texts(texts, embeddings=embs, metadata=metas)

    # Query embedding close to first/third
    q = [0.65, 0.1, 0.2, 0.0]
    res = await store.hybrid_search("hello hybrid world", q, alpha=0.7, top_k=2)

    assert len(res.documents) >= 1
    ids = [d.id for d in res.documents]
    assert isinstance(ids, list)

