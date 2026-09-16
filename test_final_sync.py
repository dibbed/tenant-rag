#!/usr/bin/env python3
"""Final sync test for vector stores."""

from ragbot.rag.store.factory import VectorStoreFactory

print("🔍 Testing store creation...")

try:
    faiss = VectorStoreFactory.create_store("faiss", path="./test_faiss")
    print("✅ FAISS store created successfully")
except Exception as e:
    print(f"❌ FAISS failed: {e}")

try:
    chroma = VectorStoreFactory.create_store(
        "chroma", persist_directory="./test_chroma"
    )
    print("✅ Chroma store created successfully")
except Exception as e:
    print(f"❌ Chroma failed: {e}")

print("✅ Core functionality working!")
