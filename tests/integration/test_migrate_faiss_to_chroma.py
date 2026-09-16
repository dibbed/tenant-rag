import pytest


pytestmark = pytest.mark.asyncio


def _has_chromadb():
    try:
        import chromadb  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_chromadb(), reason="chromadb not installed")
async def test_migrate_faiss_to_chroma(tmp_path):
    from ragbot.rag.store.faiss_store import FAISSStore
    from ragbot.utils.migration import migrate_stores, verify_migration

    # Setup FAISS in-memory and upsert some items
    src = FAISSStore(store_path=str(tmp_path / "faiss_idx"), embedding_dimension=4)
    texts = ["foo", "bar"]
    embs = [[0.1, 0.2, 0.3, 0.4], [0.2, 0.1, 0.0, 0.1]]
    metas = [{"language": "en", "page": 1}, {"language": "en", "page": 2}]
    await src.add_texts(texts, embeddings=embs, metadata=metas)

    # Migrate using factory-created stores
    out = await migrate_stores(
        "faiss",
        "chromadb",
        source_kwargs={"store_path": str(tmp_path / "faiss_idx"), "embedding_dimension": 4},
        target_kwargs={
            "persist_directory": str(tmp_path / "chroma_db"),
            "collection_name": "migrate_test",
            "embedding_dimension": 4,
        },
    )
    assert out["status"] == "ok"
    assert out["migrated"] >= 2

    ver = await verify_migration(
        "faiss",
        "chromadb",
        source_kwargs={"store_path": str(tmp_path / "faiss_idx"), "embedding_dimension": 4},
        target_kwargs={
            "persist_directory": str(tmp_path / "chroma_db"),
            "collection_name": "migrate_test",
            "embedding_dimension": 4,
        },
    )
    assert ver["target_count"] >= ver["source_count"]

