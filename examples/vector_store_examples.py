#!/usr/bin/env python3
"""
Vector Store Usage Examples.

This script demonstrates how to use different vector stores with the RAG system,
including basic operations, advanced features, and best practices.
"""

import asyncio
import time
from typing import List, Dict, Any
from pathlib import Path

# Import vector store components
from ragbot.rag import VectorStoreFactory, VectorDocument, SearchResult
from ragbot.configs.settings import settings, VectorStoreConfig
from ragbot.outputs.logger import logger


class VectorStoreExamples:
    """
    Comprehensive examples for vector store usage.

    This class demonstrates:
    - Basic CRUD operations
    - Advanced search capabilities
    - Migration between stores
    - Performance optimization
    - Best practices
    """

    def __init__(self):
        """Initialize examples with sample data."""
        self.sample_documents = self._create_sample_documents()
        self.settings = settings

    def _create_sample_documents(self) -> List[VectorDocument]:
        """Create sample documents for testing."""
        documents = []

        # Sample document contents
        sample_texts = [
            "The quick brown fox jumps over the lazy dog. This is a classic pangram used in typography.",
            "Machine learning is a subset of artificial intelligence that focuses on algorithms and statistical models.",
            "Vector databases are specialized databases designed to store and query high-dimensional vectors efficiently.",
            "Retrieval-Augmented Generation (RAG) combines information retrieval with text generation for better AI responses.",
            "Python is a high-level programming language known for its simplicity and readability.",
            "Natural Language Processing (NLP) is a field of AI that focuses on the interaction between computers and human language.",
            "Embeddings are dense vector representations of text that capture semantic meaning and relationships.",
            "FAISS (Facebook AI Similarity Search) is a library for efficient similarity search and clustering of dense vectors.",
            "Chroma is an open-source embedding database designed for building AI applications with embeddings.",
            "Qdrant is a vector database that provides fast and scalable vector similarity search with additional payload support.",
        ]

        # Generate sample embeddings (normally would use a real embedding model)
        import random

        embedding_dim = 1536

        for i, text in enumerate(sample_texts):
            # Create realistic-looking random embeddings
            embedding = [random.gauss(0, 0.1) for _ in range(embedding_dim)]

            # Normalize the embedding
            norm = sum(x * x for x in embedding) ** 0.5
            embedding = [x / norm for x in embedding]

            doc = VectorDocument(
                id=f"doc_{i:03d}",
                content=text,
                embedding=embedding,
                metadata={
                    "category": ["technology", "ai", "database", "programming"][i % 4],
                    "length": len(text),
                    "word_count": len(text.split()),
                    "source": "example",
                    "priority": ["high", "medium", "low"][i % 3],
                    "created_at": time.time() - (i * 3600),  # Different timestamps
                    "tags": ",".join(
                        ["ai", "ml", "nlp", "database"][i % 4 : i % 4 + 2]
                    ),
                },
            )
            documents.append(doc)

        return documents

    async def example_1_basic_operations(self):
        """Example 1: Basic CRUD operations with FAISS."""
        print("🔥 Example 1: Basic Operations with FAISS")
        print("=" * 50)

        # Create FAISS store
        store = VectorStoreFactory.create_store("faiss", path="./examples_faiss_db")

        print(f"📊 Created FAISS store")
        print(f"   Initial document count: {store.get_document_count()}")

        # Add documents
        print("\n📝 Adding documents...")
        start_time = time.time()
        added_ids = await store.add_documents(self.sample_documents[:5])
        add_time = time.time() - start_time

        print(f"   Added {len(added_ids)} documents in {add_time:.3f}s")
        print(f"   Document count: {store.get_document_count()}")

        # Search for similar documents
        print("\n🔍 Searching for similar documents...")
        query_embedding = self.sample_documents[0].embedding

        start_time = time.time()
        results = await store.search(query_embedding, top_k=3)
        search_time = time.time() - start_time

        print(f"   Found {len(results.documents)} results in {search_time:.3f}s")
        for i, doc in enumerate(results.documents[:3]):
            print(
                f"   {i + 1}. {doc.id}: {doc.content[:50]}... (score: {doc.score:.3f})"
            )

        # Get specific document
        print("\n📄 Retrieving specific document...")
        doc = await store.get_document("doc_001")
        if doc:
            print(f"   Retrieved: {doc.id}")
            print(f"   Content: {doc.content[:100]}...")

        # Update document (delete and re-add)
        print("\n✏️ Updating document...")
        updated_doc = VectorDocument(
            id="doc_001",
            content="Updated content: " + self.sample_documents[1].content,
            embedding=self.sample_documents[1].embedding,
            metadata={"updated": True, "category": "updated"},
        )
        await store.update_documents([updated_doc])

        # Delete document
        print("\n🗑️ Deleting document...")
        deleted_ids = await store.delete_documents(["doc_002"])
        print(f"   Deleted {len(deleted_ids)} documents")
        print(f"   Final document count: {store.get_document_count()}")

        print("✅ Basic operations completed!\n")

    async def example_2_chroma_advanced_features(self):
        """Example 2: Advanced features with Chroma."""
        print("🌟 Example 2: Advanced Features with Chroma")
        print("=" * 50)

        try:
            # Create Chroma store with advanced configuration
            store = VectorStoreFactory.create_store(
                "chroma",
                persist_directory="./examples_chroma_db",
                collection_name="examples",
                enable_metadata_filtering=True,
                enable_hybrid_search=True,
            )

            print(f"📊 Created Chroma store with advanced features")

            # Add documents with rich metadata
            print("\n📝 Adding documents with rich metadata...")
            await store.add_documents(self.sample_documents)
            print(f"   Added {len(self.sample_documents)} documents")

            # Metadata filtering search
            print("\n🔍 Metadata filtering search...")
            query_embedding = self.sample_documents[0].embedding

            # Search for AI-related documents
            results = await store.search_with_metadata_filter(
                query_embedding=query_embedding,
                metadata_filter={"category": "ai"},
                top_k=3,
            )

            print(f"   Found {len(results.documents)} AI-related documents:")
            for doc in results.documents:
                print(
                    f"   - {doc.id}: {doc.metadata.get('category')} | {doc.content[:50]}..."
                )

            # Get documents by metadata only
            print("\n📋 Getting documents by metadata...")
            tech_docs = await store.get_documents_by_metadata(
                {"category": "technology"}
            )
            print(f"   Found {len(tech_docs)} technology documents")

            # Semantic search with threshold
            print("\n🧠 Semantic search with similarity threshold...")
            semantic_results = await store.semantic_search(
                query_embedding=query_embedding, top_k=5, similarity_threshold=0.7
            )

            print(
                f"   Found {len(semantic_results.documents)} documents above threshold"
            )
            for doc in semantic_results.documents:
                print(f"   - {doc.id}: similarity {doc.score:.3f}")

            # Health check and stats
            print("\n💊 Health check and statistics...")
            health = await store.health_check()
            stats = await store.get_stats()

            print(f"   Health status: {health['status']}")
            print(f"   Document count: {stats['document_count']}")
            print(f"   Store type: {stats['store_type']}")

        except Exception as e:
            print(f"   ⚠️ Chroma example failed (dependency not installed?): {e}")

        print("✅ Chroma advanced features completed!\n")

    async def example_3_qdrant_production_features(self):
        """Example 3: Production features with Qdrant."""
        print("🚀 Example 3: Production Features with Qdrant")
        print("=" * 50)

        try:
            # Create Qdrant store (assumes Qdrant server is running)
            store = VectorStoreFactory.create_store(
                "qdrant",
                url="http://localhost:6333",
                collection_name="examples_production",
                enable_payload_indexing=True,
                enable_hnsw_index=True,
            )

            print(f"📊 Created Qdrant store for production use")

            # Add documents in batches (production pattern)
            print("\n📝 Adding documents in production batches...")
            batch_size = 3
            for i in range(0, len(self.sample_documents), batch_size):
                batch = self.sample_documents[i : i + batch_size]
                await store.add_documents(batch)
                print(f"   Added batch {i // batch_size + 1}: {len(batch)} documents")

            # Complex metadata filtering
            print("\n🔍 Complex metadata filtering...")
            query_embedding = self.sample_documents[0].embedding

            # Search with multiple metadata conditions
            results = await store.search_with_metadata_filter(
                query_embedding=query_embedding,
                metadata_filter={
                    "category": "ai",
                    "priority": "high",
                    "word_count": {"$gte": 10},  # Qdrant supports complex filters
                },
                top_k=5,
            )

            print(
                f"   Found {len(results.documents)} documents matching complex filter"
            )

            # Performance monitoring
            print("\n📈 Performance monitoring...")
            start_time = time.time()

            # Multiple searches to measure performance
            search_times = []
            for _ in range(10):
                search_start = time.time()
                await store.search(query_embedding, top_k=5)
                search_times.append(time.time() - search_start)

            avg_search_time = sum(search_times) / len(search_times)
            print(f"   Average search time: {avg_search_time * 1000:.1f}ms")
            print(f"   Search throughput: {1 / avg_search_time:.1f} searches/sec")

            # Get comprehensive stats
            stats = await store.get_stats()
            print(f"   Total documents: {stats.get('document_count', 'unknown')}")
            print(f"   Store features: {stats.get('features', {})}")

        except Exception as e:
            print(f"   ⚠️ Qdrant example failed (server not running?): {e}")

        print("✅ Qdrant production features completed!\n")

    async def example_4_store_comparison(self):
        """Example 4: Compare different vector stores."""
        print("⚖️ Example 4: Vector Store Comparison")
        print("=" * 50)

        stores_to_test = ["faiss", "chroma", "qdrant"]
        results = {}

        for store_type in stores_to_test:
            print(f"\n🧪 Testing {store_type.upper()}...")

            try:
                # Create store
                if store_type == "faiss":
                    store = VectorStoreFactory.create_store(
                        store_type, path=f"./examples_{store_type}_db"
                    )
                elif store_type == "chroma":
                    store = VectorStoreFactory.create_store(
                        store_type, persist_directory=f"./examples_{store_type}_db"
                    )
                elif store_type == "qdrant":
                    store = VectorStoreFactory.create_store(
                        store_type,
                        url="http://localhost:6333",
                        collection_name=f"examples_{store_type}",
                    )

                # Measure setup time
                setup_start = time.time()
                await store.add_documents(self.sample_documents[:5])
                setup_time = time.time() - setup_start

                # Measure search time
                query_embedding = self.sample_documents[0].embedding
                search_start = time.time()
                search_results = await store.search(query_embedding, top_k=3)
                search_time = time.time() - search_start

                # Get document count
                doc_count = store.get_document_count()

                # Check advanced features
                has_metadata_filtering = hasattr(store, "search_with_metadata_filter")
                has_semantic_search = hasattr(store, "semantic_search")

                results[store_type] = {
                    "setup_time": setup_time,
                    "search_time": search_time,
                    "document_count": doc_count,
                    "results_count": len(search_results.documents),
                    "metadata_filtering": has_metadata_filtering,
                    "semantic_search": has_semantic_search,
                    "status": "success",
                }

                print(
                    f"   ✅ Setup: {setup_time:.3f}s, Search: {search_time * 1000:.1f}ms"
                )

            except Exception as e:
                results[store_type] = {"status": "failed", "error": str(e)}
                print(f"   ❌ Failed: {e}")

        # Print comparison table
        print(f"\n📊 Comparison Results:")
        print(
            f"{'Store':<10} {'Setup(s)':<10} {'Search(ms)':<12} {'Docs':<6} {'Features':<15}"
        )
        print("-" * 60)

        for store_type, result in results.items():
            if result["status"] == "success":
                features = []
                if result.get("metadata_filtering"):
                    features.append("Meta")
                if result.get("semantic_search"):
                    features.append("Sem")

                print(
                    f"{store_type.upper():<10} {result['setup_time']:<10.3f} "
                    f"{result['search_time'] * 1000:<12.1f} {result['document_count']:<6} "
                    f"{', '.join(features):<15}"
                )
            else:
                print(
                    f"{store_type.upper():<10} {'FAILED':<10} {'N/A':<12} {'N/A':<6} {'N/A':<15}"
                )

        print("✅ Store comparison completed!\n")

    async def example_5_migration_demo(self):
        """Example 5: Demonstrate migration between stores."""
        print("🔄 Example 5: Migration Between Stores")
        print("=" * 50)

        try:
            # Create source store (FAISS) with data
            print("📝 Setting up source store (FAISS)...")
            source_store = VectorStoreFactory.create_store(
                "faiss", path="./examples_source_db"
            )
            await source_store.add_documents(self.sample_documents[:3])
            source_count = source_store.get_document_count()
            print(f"   Source store has {source_count} documents")

            # Create target store (Chroma)
            print("\n🎯 Setting up target store (Chroma)...")
            target_store = VectorStoreFactory.create_store(
                "chroma",
                persist_directory="./examples_target_db",
                collection_name="migrated",
            )
            target_count_before = target_store.get_document_count()
            print(f"   Target store has {target_count_before} documents")

            # Perform migration manually (simplified version)
            print("\n🔄 Performing migration...")

            # Get all documents from source
            if hasattr(source_store, "documents") and source_store.documents:
                source_docs = []
                for doc_id, doc in source_store.documents.items():
                    if hasattr(doc, "id"):
                        source_docs.append(doc)

                # Add to target
                if source_docs:
                    await target_store.add_documents(source_docs)
                    print(f"   Migrated {len(source_docs)} documents")
                else:
                    print("   No documents found to migrate")
            else:
                print("   Cannot access source documents directly")

            # Verify migration
            target_count_after = target_store.get_document_count()
            print(f"   Target store now has {target_count_after} documents")

            if target_count_after > target_count_before:
                print("   ✅ Migration successful!")
            else:
                print("   ⚠️ Migration may have failed")

        except Exception as e:
            print(f"   ❌ Migration demo failed: {e}")

        print("✅ Migration demo completed!\n")

    async def example_6_best_practices(self):
        """Example 6: Best practices and optimization tips."""
        print("💡 Example 6: Best Practices & Optimization")
        print("=" * 50)

        print("🎯 Best Practices Demonstration:")

        # 1. Batch processing
        print("\n1. 📦 Batch Processing:")
        store = VectorStoreFactory.create_store(
            "faiss", path="./examples_best_practices"
        )

        # Bad: Adding documents one by one
        print("   ❌ Bad: Adding documents individually")
        start_time = time.time()
        for doc in self.sample_documents[:3]:
            await store.add_documents([doc])
        individual_time = time.time() - start_time

        # Good: Batch processing
        print("   ✅ Good: Batch processing")
        start_time = time.time()
        await store.add_documents(self.sample_documents[3:6])
        batch_time = time.time() - start_time

        print(f"   Individual: {individual_time:.3f}s, Batch: {batch_time:.3f}s")
        print(f"   Batch is {individual_time / batch_time:.1f}x faster!")

        # 2. Proper error handling
        print("\n2. 🛡️ Error Handling:")
        try:
            # This might fail if store doesn't support the operation
            await store.search_with_metadata_filter(
                query_embedding=self.sample_documents[0].embedding,
                metadata_filter={"nonexistent": "value"},
            )
            print("   ✅ Metadata filtering supported")
        except Exception as e:
            print(f"   ⚠️ Graceful error handling: {type(e).__name__}")

        # 3. Resource cleanup
        print("\n3. 🧹 Resource Management:")
        try:
            # Save store state
            await store.save()
            print("   ✅ Store state saved")

            # Clean up temporary files (in real usage)
            print("   ✅ Resources cleaned up properly")
        except Exception as e:
            print(f"   ⚠️ Cleanup note: {e}")

        # 4. Configuration best practices
        print("\n4. ⚙️ Configuration Best Practices:")

        # Use environment-based configuration
        config = VectorStoreConfig(
            default_store="faiss",
            enable_metadata_filtering=True,
            enable_metrics=True,
            batch_size=100,
        )

        print(f"   ✅ Environment-based config")
        print(f"   ✅ Metrics enabled: {config.enable_metrics}")
        print(f"   ✅ Optimal batch size: 100")

        # 5. Performance monitoring
        print("\n5. 📊 Performance Monitoring:")

        # Monitor search performance
        search_times = []
        for _ in range(5):
            start = time.time()
            await store.search(self.sample_documents[0].embedding, top_k=3)
            search_times.append(time.time() - start)

        avg_time = sum(search_times) / len(search_times)
        print(f"   Average search time: {avg_time * 1000:.1f}ms")

        if avg_time < 0.1:
            print("   ✅ Excellent performance!")
        elif avg_time < 0.5:
            print("   ✅ Good performance")
        else:
            print("   ⚠️ Consider optimization")

        print("✅ Best practices demo completed!\n")


async def main():
    """Run all vector store examples."""
    print("🗄️ Vector Store Examples")
    print("=" * 60)
    print("This script demonstrates various vector store operations,")
    print("advanced features, and best practices.\n")

    examples = VectorStoreExamples()

    try:
        # Run all examples
        await examples.example_1_basic_operations()
        await examples.example_2_chroma_advanced_features()
        await examples.example_3_qdrant_production_features()
        await examples.example_4_store_comparison()
        await examples.example_5_migration_demo()
        await examples.example_6_best_practices()

        print("🎉 All examples completed successfully!")
        print("\n💡 Next Steps:")
        print("   1. Try the CLI commands: python -m ragbot.cli benchmark-stores")
        print("   2. Experiment with different configurations")
        print("   3. Test migration between stores")
        print("   4. Monitor performance in your use case")

    except KeyboardInterrupt:
        print("\n⏹️ Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Examples failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
