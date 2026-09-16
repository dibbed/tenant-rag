import pytest


pytestmark = pytest.mark.asyncio


def _has_qdrant():
    try:
        import qdrant_client  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_qdrant(), reason="qdrant-client not installed")
async def test_migrate_faiss_to_qdrant(tmp_path):
    from ragbot.rag.store.faiss_store import FAISSStore
    from ragbot.utils.migration import migrate_stores, verify_migration

    src = FAISSStore(store_path=str(tmp_path / "faiss_idx"), embedding_dimension=4)
    texts = ["foo", "bar", "baz"]
    embs = [[0.1, 0.2, 0.3, 0.4], [0.2, 0.1, 0.0, 0.1], [0.05, 0.2, 0.31, 0.4]]
    metas = [{"language": "en"} for _ in texts]
    await src.add_texts(texts, embeddings=embs, metadata=metas)

    out = await migrate_stores(
        "faiss",
        "qdrant",
        source_kwargs={"store_path": str(tmp_path / "faiss_idx"), "embedding_dimension": 4},
        target_kwargs={"path": str(tmp_path / "qdrant"), "collection_name": "migrate_test", "embedding_dimension": 4},
    )
    assert out["status"] in {"ok", "unsupported"}
    if out["status"] == "ok":
        ver = await verify_migration(
            "faiss",
            "qdrant",
            source_kwargs={"store_path": str(tmp_path / "faiss_idx"), "embedding_dimension": 4},
            target_kwargs={"path": str(tmp_path / "qdrant"), "collection_name": "migrate_test", "embedding_dimension": 4},
        )
        assert ver["target_count"] >= ver["source_count"]

