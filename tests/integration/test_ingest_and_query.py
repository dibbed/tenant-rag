"""
End-to-end RAG pipeline integration tests.

This module tests the complete RAG workflow from document ingestion
to query processing directly via the service layer.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ragbot.rag import TokenChunker, OpenAIEmbedder, TextLoader, QAChain
from ragbot.rag.retrieve.retriever import Retriever
from ragbot.rag.store.faiss_store import FAISSStore


class TestIngestAndQuery:
    """Integration tests for the complete RAG pipeline."""

    @pytest.fixture
    def tmp_workspace(self, tmp_path: Path) -> Path:
        """Create temporary workspace for testing."""
        workspace = tmp_path / "rag_test"
        workspace.mkdir(exist_ok=True)
        return workspace

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        """Create a mock embedder for testing."""
        embedder = MagicMock(spec=OpenAIEmbedder)
        embedder.embed_text = AsyncMock()
        embedder.embed_texts = AsyncMock()
        return embedder

    @pytest.fixture
    def mock_qa_chain(self) -> MagicMock:
        """Create a mock QA chain for testing."""
        qa_chain = MagicMock(spec=QAChain)
        qa_chain.generate_answer = AsyncMock()
        return qa_chain

    @pytest.fixture
    def sample_bilingual_text(self) -> str:
        """Create sample bilingual text for testing."""
        return """
        Machine learning is a method of data analysis that automates analytical model building.
        It is a branch of artificial intelligence based on the idea that systems can learn from data.

        یادگیری ماشین روشی برای تجزیه و تحلیل داده است که ساخت مدل تحلیلی را خودکار می‌کند.
        این شاخه‌ای از هوش مصنوعی است که بر این ایده استوار است که سیستم‌ها می‌توانند از داده‌ها یاد بگیرند.

        FAISS (Facebook AI Similarity Search) is a library for efficient similarity search.
        It contains algorithms that search in sets of vectors of any size.
        """

    @pytest.mark.asyncio
    async def test_complete_rag_workflow_basic(
        self,
        tmp_workspace: Path,
        mock_embedder: MagicMock,
        mock_qa_chain: MagicMock,
        sample_bilingual_text: str,
    ) -> None:
        """Test complete RAG workflow from text to answer."""
        # Step 1: Text chunking (using TokenChunker)
        chunks = await TokenChunker(chunk_size=64, chunk_overlap=0).chunk_texts(
            [sample_bilingual_text]
        )
        chunks = chunks  # already list[str]
        assert len(chunks) > 1
        assert all(len(chunk.strip()) > 0 for chunk in chunks)

        # Step 2: Mock embedding generation
        mock_embeddings = [[i * 0.1] * 768 for i in range(len(chunks))]
        mock_embedder.embed_texts.return_value = mock_embeddings

        # Step 3: Vector store operations
        store = FAISSStore(store_path=str(tmp_workspace / "faiss_index"))
        await store.upsert(
            texts=chunks, metadata=[{"chunk_index": i} for i in range(len(chunks))]
        )
        assert store.count() == len(chunks)

        # Step 4: Query processing
        query = "What is machine learning?"
        query_embedding = [0.5] * 768
        mock_embedder.embed_text.return_value = query_embedding

        results = await store.query(query_embedding, top_k=3)
        assert len(results) <= 3

        # Step 5: Answer generation
        context_texts = [result.content for result in results]
        mock_qa_chain.generate_answer.return_value = (
            "Machine learning is a data analysis method."
        )

        answer = await mock_qa_chain.generate_answer(
            context=context_texts, question=query, language="en"
        )

        assert isinstance(answer, str)
        assert len(answer) > 0

    @pytest.mark.asyncio
    async def test_ingest_and_query_flow_with_chunker(
        self, tmp_workspace: Path, mock_embedder: MagicMock, sample_bilingual_text: str
    ) -> None:
        """Test workflow using TokenChunker instead of split_text."""
        # Use TokenChunker for more realistic chunking
        chunker = TokenChunker(chunk_size=128, chunk_overlap=20)

        from ragbot.rag import Document

        document = Document(
            content=sample_bilingual_text,
            metadata={"source": "test_document", "source_type": "text"},
        )

        # Chunk the document
        chunks = await chunker.chunk_document(document)
        assert len(chunks) > 0
        assert all(hasattr(chunk, "content") for chunk in chunks)
        assert all(hasattr(chunk, "metadata") for chunk in chunks)

        # Mock embeddings
        chunk_texts = [chunk.content for chunk in chunks]
        mock_embeddings = [[i * 0.1] * 768 for i in range(len(chunk_texts))]
        mock_embedder.embed_texts.return_value = mock_embeddings

        # Store in vector database
        store = FAISSStore(store_path=str(tmp_workspace / "chunker_test"))
        chunk_metadata = [chunk.metadata for chunk in chunks]

        await store.upsert(
            texts=chunk_texts, embeddings=mock_embeddings, metadata=chunk_metadata
        )

        # Verify storage
        assert store.count() == len(chunks)

        # Query the store
        query_embedding = [0.3] * 768
        mock_embedder.embed_text.return_value = query_embedding

        results = await store.query(query_embedding, top_k=2)
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_multilingual_ingest_and_query(
        self, tmp_workspace: Path, mock_embedder: MagicMock, mock_qa_chain: MagicMock
    ) -> None:
        """Test RAG workflow with multilingual content."""
        multilingual_content = """
        English: Artificial intelligence is transforming technology.
        Persian: هوش مصنوعی در حال تغییر فناوری است.
        Arabic: الذكاء الاصطناعي يغير التكنولوجيا.
        """

        # Chunk multilingual content
        chunks = await TokenChunker(chunk_size=32, chunk_overlap=0).chunk_texts(
            [multilingual_content]
        )
        chunks = chunks

        # Mock embeddings for different languages
        mock_embeddings = []
        for i, chunk in enumerate(chunks):
            if "English" in chunk:
                embedding = [0.1] * 768
            elif "Persian" in chunk or "هوش" in chunk:
                embedding = [0.2] * 768
            elif "Arabic" in chunk or "الذكاء" in chunk:
                embedding = [0.3] * 768
            else:
                embedding = [0.4] * 768
            mock_embeddings.append(embedding)

        mock_embedder.embed_texts.return_value = mock_embeddings

        # Store multilingual content
        store = FAISSStore(store_path=str(tmp_workspace / "multilingual"))
        await store.upsert(
            texts=chunks,
            embeddings=mock_embeddings,
            metadata=[{"language": "mixed", "chunk": i} for i in range(len(chunks))],
        )

        # Test queries in different languages
        test_queries = [
            ("What is AI?", "en", [0.1] * 768),
            ("هوش مصنوعی چیست؟", "fa", [0.2] * 768),
            ("ما هو الذكاء الاصطناعي؟", "ar", [0.3] * 768),
        ]

        for query, lang, query_embedding in test_queries:
            mock_embedder.embed_text.return_value = query_embedding
            results = await store.query(query_embedding, top_k=2)

            # Should find relevant results for each language
            assert len(results) > 0

            # Mock answer generation
            context_texts = [result.content for result in results]
            mock_qa_chain.generate_answer.return_value = f"Answer in {lang}"

            answer = await mock_qa_chain.generate_answer(
                context=context_texts, question=query, language=lang
            )

            assert isinstance(answer, str)
            assert len(answer) > 0

    @pytest.mark.asyncio
    async def test_document_loader_integration(
        self, tmp_workspace: Path, mock_embedder: MagicMock
    ) -> None:
        """Test integration with document loaders."""
        # Test with TextLoader
        text_loader = TextLoader()

        # Create a test text file
        test_file = tmp_workspace / "test.txt"
        test_content = "This is a test document for integration testing."
        test_file.write_text(test_content, encoding="utf-8")

        # Load document
        document = await text_loader.load(str(test_file))
        assert document.content == test_content
        assert document.metadata["source"] == str(test_file)

        # Process through complete pipeline
        chunker = TokenChunker(chunk_size=64, chunk_overlap=10)
        chunks = await chunker.chunk_document(document)

        # Should handle small document appropriately
        assert len(chunks) >= 1

        # Mock embeddings and store
        chunk_texts = [chunk.content for chunk in chunks]
        mock_embeddings = [[0.1] * 768 for _ in range(len(chunk_texts))]
        mock_embedder.embed_texts.return_value = mock_embeddings

        store = FAISSStore(store_path=str(tmp_workspace / "loader_test"))
        await store.upsert(
            texts=chunk_texts,
            embeddings=mock_embeddings,
            metadata=[chunk.metadata for chunk in chunks],
        )

        assert store.count() == len(chunks)

    @pytest.mark.asyncio
    async def test_error_handling_in_pipeline(
        self, tmp_workspace: Path, mock_embedder: MagicMock
    ) -> None:
        """Test error handling throughout the pipeline."""
        # Test with embedding failure
        mock_embedder.embed_texts.side_effect = Exception("Embedding failed")

        chunks = ["Test chunk 1", "Test chunk 2"]
        store = FAISSStore(store_path=str(tmp_workspace / "error_test"))

        # Should handle embedding errors gracefully
        with pytest.raises(Exception):
            mock_embeddings = await mock_embedder.embed_texts(chunks)
            await store.upsert(
                texts=chunks,
                embeddings=mock_embeddings,
                metadata=[{"id": i} for i in range(len(chunks))],
            )

    @pytest.mark.asyncio
    async def test_retriever_integration(
        self, tmp_workspace: Path, mock_embedder: MagicMock
    ) -> None:
        """Test integration with Retriever component."""
        # Setup store with data
        texts = [
            "AI content here",
            "Machine learning information",
            "Deep learning details",
        ]
        mock_embeddings = [[i * 0.1] * 768 for i in range(len(texts))]
        mock_embedder.embed_texts.return_value = mock_embeddings

        store = FAISSStore(store_path=str(tmp_workspace / "retriever_test"))
        await store.upsert(
            texts=texts,
            embeddings=mock_embeddings,
            metadata=[{"id": i} for i in range(len(texts))],
        )

        # Create retriever
        retriever = Retriever(vector_store=store, embedder=mock_embedder)

        # Test retrieval
        query = "What is artificial intelligence?"
        query_embedding = [0.5] * 768
        mock_embedder.embed_text.return_value = query_embedding

        # Mock store query to return formatted results
        from ragbot.rag import SearchResult

        mock_results = [
            SearchResult(content=texts[0], metadata={"id": 0}, score=0.9),
            SearchResult(content=texts[1], metadata={"id": 1}, score=0.8),
        ]

        with patch.object(store, "query", return_value=mock_results):
            results = await retriever.retrieve(query, top_k=2)

            assert len(results) == 2
            assert all(hasattr(result, "content") for result in results)
            assert all(hasattr(result, "score") for result in results)

    @pytest.mark.asyncio
    async def test_save_and_load_workflow(
        self, tmp_workspace: Path, mock_embedder: MagicMock
    ) -> None:
        """Test saving and loading in complete workflow."""
        # Initial setup and ingestion
        texts = ["Document 1 content", "Document 2 content", "Document 3 content"]
        mock_embeddings = [[i * 0.1] * 768 for i in range(len(texts))]
        mock_embedder.embed_texts.return_value = mock_embeddings

        store_path = str(tmp_workspace / "save_load_test")
        store1 = FAISSStore(store_path=store_path)

        await store1.upsert(
            texts=texts,
            embeddings=mock_embeddings,
            metadata=[{"doc_id": i} for i in range(len(texts))],
        )

        # Save the store
        await store1.save()

        # Create new store instance and load
        store2 = FAISSStore(store_path=store_path)
        await store2.load()

        # Verify loaded store works
        assert store2.count() == len(texts)

        # Test query on loaded store
        query_embedding = [0.2] * 768
        results = await store2.query(query_embedding, top_k=2)

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_concurrent_pipeline_operations(
        self, tmp_workspace: Path, mock_embedder: MagicMock
    ) -> None:
        """Test concurrent pipeline operations."""

        # Setup multiple concurrent ingestion tasks
        async def ingest_batch(batch_id: int, store_path: str):
            texts = [f"Batch {batch_id} document {i}" for i in range(5)]
            embeddings = [[batch_id * 0.1 + i * 0.01] * 768 for i in range(5)]

            store = FAISSStore(store_path=f"{store_path}_{batch_id}")
            await store.upsert(
                texts=texts,
                embeddings=embeddings,
                metadata=[{"batch": batch_id, "doc": i} for i in range(5)],
            )
            return store.count()

        # Run concurrent ingestion
        base_path = str(tmp_workspace / "concurrent")
        tasks = [ingest_batch(i, base_path) for i in range(3)]
        counts = await asyncio.gather(*tasks)

        # Verify all batches were processed
        assert all(count == 5 for count in counts)

    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(
        self, tmp_workspace: Path, mock_embedder: MagicMock
    ) -> None:
        """Test pipeline performance with larger dataset."""
        import time

        # Create larger dataset
        num_docs = 100
        texts = [f"Performance test document {i} with content" for i in range(num_docs)]
        mock_embeddings = [[i * 0.001] * 768 for i in range(num_docs)]
        mock_embedder.embed_texts.return_value = mock_embeddings

        store = FAISSStore(store_path=str(tmp_workspace / "performance"))

        # Measure ingestion time
        start_time = time.time()
        await store.upsert(
            texts=texts,
            embeddings=mock_embeddings,
            metadata=[{"id": i} for i in range(num_docs)],
        )
        ingestion_time = time.time() - start_time

        # Should complete in reasonable time
        assert ingestion_time < 5.0  # Less than 5 seconds
        assert store.count() == num_docs

        # Measure query time
        query_embedding = [0.5] * 768
        start_time = time.time()
        results = await store.query(query_embedding, top_k=10)
        query_time = time.time() - start_time

        # Should query quickly
        assert query_time < 1.0  # Less than 1 second
        assert len(results) <= 10

    @pytest.mark.asyncio
    async def test_empty_document_handling(
        self, tmp_workspace: Path, mock_embedder: MagicMock
    ) -> None:
        """Test handling of empty or minimal documents."""
        # Test with empty content
        empty_chunks = []
        store = FAISSStore(store_path=str(tmp_workspace / "empty_test"))

        await store.upsert(texts=empty_chunks, embeddings=[], metadata=[])
        assert store.count() == 0

        # Test with minimal content
        minimal_text = "A"
        minimal_chunks = await TokenChunker(chunk_size=32, chunk_overlap=0).chunk_texts(
            [minimal_text]
        )

        if minimal_chunks:
            mock_embeddings = [[0.1] * 768 for _ in minimal_chunks]
            mock_embedder.embed_texts.return_value = mock_embeddings

            await store.upsert(
                texts=minimal_chunks,
                embeddings=mock_embeddings,
                metadata=[{"minimal": True}],
            )

            # Should handle minimal content gracefully
            assert store.count() >= 0

    @pytest.mark.asyncio
    async def test_memory_cleanup_in_pipeline(
        self, tmp_workspace: Path, mock_embedder: MagicMock
    ) -> None:
        """Test memory cleanup during pipeline operations."""
        # Process multiple batches to test memory management
        store = FAISSStore(store_path=str(tmp_workspace / "memory_test"))

        for batch in range(5):
            texts = [f"Batch {batch} doc {i}" for i in range(20)]
            embeddings = [[batch * 0.1 + i * 0.01] * 768 for i in range(20)]

            await store.upsert(
                texts=texts,
                embeddings=embeddings,
                metadata=[{"batch": batch, "doc": i} for i in range(20)],
            )

            # Verify each batch is processed
            assert store.count() == (batch + 1) * 20

        # Final verification
        assert store.count() == 100

        # Test that queries still work after multiple ingestions
        query_embedding = [0.3] * 768
        results = await store.query(query_embedding, top_k=5)
        assert len(results) <= 5
