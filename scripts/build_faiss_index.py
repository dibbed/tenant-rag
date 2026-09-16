"""
Utility to build/verify a FAISS vector index end-to-end.

- Clears/creates a target path
- Adds sample documents (or from a JSONL file if provided)
- Saves, reloads, verifies search
- Performs update/delete without full rebuild (IDMap-based)

Usage:
  python scripts/build_faiss_index.py --path ./data/vector_store/e2e_build \
      [--jsonl ./data/docs.jsonl]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
from typing import Any, Dict, List

from ragbot.rag.store.faiss_store import FAISSVectorStore
from ragbot.rag import VectorDocument


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    items.append(obj)
            except json.JSONDecodeError:
                continue
    return items


async def _build(path: str, jsonl: str | None) -> None:
    # Clean/prepare
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)

    store = FAISSVectorStore(index_path=path)

    # Prepare documents
    docs: List[VectorDocument] = []
    if jsonl:
        rows = _load_jsonl(jsonl)
        for i, row in enumerate(rows):
            text = str(row.get("content", row.get("text", f"doc {i}")))
            emb = row.get("embedding", None)
            if not isinstance(emb, list):
                # Fallback to zero vectors; real embedding should be provided via pipeline
                emb = [0.0] * store.embedding_dimension
            meta = row.get("metadata", {})
            docs.append(
                VectorDocument(
                    id=row.get("id", f"doc_{i}"),
                    content=text,
                    embedding=emb,
                    metadata=meta,
                )
            )
    else:
        # Sample Persian texts as placeholders
        docs = [
            VectorDocument(
                id="a1",
                content="قهوه عالی است",
                embedding=[0.1] * store.embedding_dimension,
                metadata={},
            ),
            VectorDocument(
                id="b2",
                content="چای هم خوشمزه است",
                embedding=[0.1] * store.embedding_dimension,
                metadata={},
            ),
            VectorDocument(
                id="c3",
                content="هوای امروز بارانی",
                embedding=[0.1] * store.embedding_dimension,
                metadata={},
            ),
        ]

    # Add and save
    await store.add_documents(docs)
    await store.save()

    # Reload new instance and verify search
    store2 = FAISSVectorStore(index_path=path)
    await store2.load(path)

    # Use a simple query vector
    q_vec = [0.1] * store2.embedding_dimension
    res1 = await store2.search(q_vec, top_k=5)
    print("INIT", len(res1.documents), [d.id for d in res1.documents])

    # Update first doc (if any)
    if res1.documents:
        top = res1.documents[0]
        nd = VectorDocument(
            id=top.id,
            content=top.content,
            embedding=[0.2] * store2.embedding_dimension,
            metadata=top.metadata,
        )
        await store2.update_documents([nd])

    # Delete last doc (if any)
    if res1.documents:
        await store2.delete_documents([res1.documents[-1].id])

    res2 = await store2.search([0.2] * store2.embedding_dimension, top_k=5)
    print("AFTER", len(res2.documents), [d.id for d in res2.documents])

    await store2.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/verify FAISS vector index")
    parser.add_argument("--path", required=True, help="Target index path")
    parser.add_argument(
        "--jsonl", help="Optional JSONL file with {id, content, embedding, metadata}"
    )
    args = parser.parse_args()

    asyncio.run(_build(args.path, args.jsonl))


if __name__ == "__main__":
    main()
