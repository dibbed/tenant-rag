"""
Manual E2E test runner - run this to verify E2E tests work.
Output is written to manual_e2e_result.txt in the same directory.
"""
import asyncio
import sys
import tempfile
from pathlib import Path

OUTPUT_FILE = Path(__file__).resolve().parent / "manual_e2e_result.txt"
RESULTS = []


def log(msg: str):
    print(msg)
    RESULTS.append(msg)


async def run_real_e2e():
    """Run real E2E test logic (FAISS add/search/update/delete)."""
    log("=== Starting Manual E2E Test ===\n")

    try:
        from ragbot.rag.store.base import VectorDocument
        from ragbot.rag.store.faiss_store import FAISSVectorStore

        log("[OK] Imports successful")

        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "faiss_index"
            store_path.mkdir(exist_ok=True)

            store = FAISSVectorStore(
                index_path=str(store_path),
                embedding_dimension=384,
            )
            log("[OK] FAISSVectorStore created")

            docs = [
                VectorDocument(
                    id="doc_1",
                    content="Machine learning is a subset of AI.",
                    embedding=[0.1] * 384,
                    metadata={"category": "AI"},
                ),
                VectorDocument(
                    id="doc_2",
                    content="Deep learning uses neural networks.",
                    embedding=[0.2] * 384,
                    metadata={"category": "AI"},
                ),
            ]

            added = await store.add_documents(docs)
            assert len(added) == 2, f"Expected 2 added, got {len(added)}"
            assert store.get_document_count() == 2
            log("[OK] add_documents: 2 docs added")

            results = await store.search([0.15] * 384, top_k=5)
            assert len(results.documents) >= 1
            log(f"[OK] search: {len(results.documents)} results")

            filtered = await store.search_with_metadata_filter(
                query_embedding=[0.15] * 384,
                metadata_filter={"category": "AI"},
                top_k=10,
            )
            assert len(filtered.documents) == 2
            log(f"[OK] search_with_metadata_filter: {len(filtered.documents)} results")

            updated_doc = VectorDocument(
                id="doc_1",
                content="Machine learning is a powerful subset of AI.",
                embedding=[0.11] * 384,
                metadata={"category": "AI", "updated": True},
            )
            updated_ids = await store.update_documents([updated_doc])
            assert "doc_1" in updated_ids
            log("[OK] update_documents: doc_1 updated")

            retrieved = await store.get_document("doc_1")
            assert "powerful" in retrieved.content
            log("[OK] get_document: content verified")

            deleted = await store.delete_documents(["doc_2"])
            assert "doc_2" in deleted
            assert store.get_document_count() == 1
            log("[OK] delete_documents: doc_2 removed")

            await store.clear()
            assert store.get_document_count() == 0
            log("[OK] clear: store emptied")

        log("\n=== ALL E2E TESTS PASSED ===")
        return True

    except Exception as e:
        log(f"\n[FAIL] Error: {e}")
        import traceback
        log(traceback.format_exc())
        return False


def main():
    success = asyncio.run(run_real_e2e())
    output = "\n".join(RESULTS)
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"\nOutput written to: {OUTPUT_FILE}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
