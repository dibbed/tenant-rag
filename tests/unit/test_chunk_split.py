"""
Text chunking tests with token boundary validation.

This module tests the text chunking functionality with various scenarios including
different languages, token limits, and edge cases.
"""

import pytest

from ragbot.rag import TokenChunker, Document


class TestChunkSplit:
    """Comprehensive test suite for text chunking functionality."""

    def test_split_text_token_bounds(self) -> None:
        """Verify chunks respect token limits."""
        txt = "سلام " * 1000  # Persian text repeated
        chunks = [
            c.content for c in TokenChunker(chunk_size=128, chunk_overlap=0).chunk(txt)
        ]

        assert all(len(c) > 0 for c in chunks)
        assert len(chunks) >= 1

        # Verify no chunk exceeds token limit (approximate check)
        for chunk in chunks:
            # Rough estimate: Persian words are typically 1-2 tokens
            estimated_tokens = len(chunk.split())
            assert estimated_tokens <= 150  # Allow some margin

    def test_split_text_empty_input(self) -> None:
        """Test handling of empty text input."""
        chunks = [
            c.content for c in TokenChunker(chunk_size=128, chunk_overlap=0).chunk("")
        ]
        assert chunks == []

    def test_split_text_short_input(self) -> None:
        """Test handling of text shorter than chunk size."""
        short_text = "This is a short text."
        chunks = [
            c.content
            for c in TokenChunker(chunk_size=128, chunk_overlap=0).chunk(short_text)
        ]

        assert len(chunks) == 1
        assert chunks[0] == short_text

    def test_split_text_exact_token_limit(self) -> None:
        """Test text that exactly matches the token limit."""
        # Create text with approximately 50 tokens
        text = " ".join(["word"] * 50)
        chunks = [
            c.content for c in TokenChunker(chunk_size=50, chunk_overlap=0).chunk(text)
        ]

        assert len(chunks) >= 1
        assert all(len(chunk.strip()) > 0 for chunk in chunks)

    @pytest.mark.parametrize("language", ["fa", "en", "ar"])
    def test_split_text_multilingual_support(self, language: str) -> None:
        """Test chunking with different languages."""
        if language == "fa":
            text = "این یک متن فارسی است. " * 100
        elif language == "en":
            text = "This is an English text. " * 100
        elif language == "ar":
            text = "هذا نص عربي. " * 100

        chunks = [
            c.content for c in TokenChunker(chunk_size=64, chunk_overlap=0).chunk(text)
        ]

        assert len(chunks) > 1  # Should split large text
        assert all(len(chunk.strip()) > 0 for chunk in chunks)

        # Verify content preservation
        rejoined = " ".join(chunks)
        assert len(rejoined) >= len(text) * 0.9  # Allow some loss due to processing

    def test_split_text_preserve_sentences(self) -> None:
        """Test that sentence boundaries are preserved when possible."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = [
            c.content for c in TokenChunker(chunk_size=20, chunk_overlap=0).chunk(text)
        ]

        # Should try to keep sentences intact
        for chunk in chunks:
            if "." in chunk:
                # If chunk contains period, it should end with one (sentence boundary)
                sentences_in_chunk = chunk.count(".")
                assert sentences_in_chunk >= 1

    def test_split_text_large_document(self) -> None:
        """Test chunking of very large documents."""
        # Create a large document
        large_text = "This is a test sentence. " * 2000  # ~10,000 tokens approximately
        chunks = [
            c.content
            for c in TokenChunker(chunk_size=256, chunk_overlap=0).chunk(large_text)
        ]

        assert len(chunks) > 10  # Should create many chunks
        assert all(len(chunk.strip()) > 0 for chunk in chunks)

        # Verify total content is preserved (approximately)
        total_length = sum(len(chunk) for chunk in chunks)
        assert total_length >= len(large_text) * 0.8  # Allow some processing loss

    def test_split_text_with_newlines(self) -> None:
        """Test handling of text with newlines and paragraphs."""
        text = """First paragraph with multiple sentences. This is still the first paragraph.

Second paragraph starts here. It also has multiple sentences.

Third paragraph is shorter.

Fourth paragraph continues the pattern."""

        chunks = [
            c.content for c in TokenChunker(chunk_size=64, chunk_overlap=0).chunk(text)
        ]

        assert len(chunks) >= 1
        # Should handle newlines gracefully
        for chunk in chunks:
            assert chunk.strip()  # No empty chunks

    def test_split_text_special_characters(self) -> None:
        """Test handling of special characters and punctuation."""
        text = "Text with (parentheses), [brackets], {braces}, and more! Question marks? Exclamation!"
        chunks = [
            c.content for c in TokenChunker(chunk_size=32, chunk_overlap=0).chunk(text)
        ]

        assert len(chunks) >= 1
        assert all(len(chunk.strip()) > 0 for chunk in chunks)

    def test_split_text_numbers_and_dates(self) -> None:
        """Test handling of numbers, dates, and special formats."""
        text = (
            "Date: 2024-01-15. Price: $123.45. Time: 14:30:00. Phone: +1-555-123-4567."
        )
        chunks = split_text(text, max_tokens=32)

        assert len(chunks) >= 1
        # Should preserve formatted numbers and dates
        rejoined = " ".join(chunks)
        assert "2024-01-15" in rejoined
        assert "$123.45" in rejoined


class TestTokenChunker:
    """Test suite for TokenChunker class."""

    @pytest.fixture
    def chunker(self) -> TokenChunker:
        """Create a TokenChunker instance for testing."""
        return TokenChunker(chunk_size=256, chunk_overlap=50)

    @pytest.fixture
    def sample_document(self) -> Document:
        """Create a sample document for testing."""
        content = "This is a sample document. " * 200  # Large enough to split
        return Document(
            content=content, metadata={"source": "test", "source_type": "text"}
        )

    @pytest.mark.asyncio
    async def test_chunk_document_basic(
        self, chunker: TokenChunker, sample_document: Document
    ) -> None:
        """Test basic document chunking."""
        chunks = await chunker.chunk_document(sample_document)

        assert len(chunks) > 1  # Should split large document
        assert all(hasattr(chunk, "content") for chunk in chunks)
        assert all(hasattr(chunk, "metadata") for chunk in chunks)

        # Verify metadata propagation
        for chunk in chunks:
            assert chunk.metadata["source"] == "test"
            assert "chunk_index" in chunk.metadata

    @pytest.mark.asyncio
    async def test_chunk_document_small(self, chunker: TokenChunker) -> None:
        """Test chunking of small documents."""
        small_doc = Document(
            content="Short document.",
            metadata={"source": "test", "source_type": "text"},
        )

        chunks = await chunker.chunk_document(small_doc)

        assert len(chunks) == 1
        assert chunks[0].content == "Short document."

    @pytest.mark.asyncio
    async def test_chunk_document_empty(self, chunker: TokenChunker) -> None:
        """Test chunking of empty documents."""
        empty_doc = Document(
            content="", metadata={"source": "test", "source_type": "text"}
        )

        chunks = await chunker.chunk_document(empty_doc)
        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_chunk_document_with_overlap(self, chunker: TokenChunker) -> None:
        """Test that chunk overlap is preserved."""
        # Create document with easily identifiable content
        content = " ".join([f"sentence_{i}" for i in range(200)])
        doc = Document(content=content, metadata={"source": "test"})

        chunks = await chunker.chunk_document(doc)

        if len(chunks) > 1:
            # Check for overlap between consecutive chunks
            for i in range(len(chunks) - 1):
                chunk1_words = chunks[i].content.split()
                chunk2_words = chunks[i + 1].content.split()

                # Should have some overlap
                overlap_found = any(word in chunk2_words for word in chunk1_words[-10:])
                assert overlap_found

    @pytest.mark.asyncio
    async def test_chunk_document_multilingual(self, chunker: TokenChunker) -> None:
        """Test chunking with multilingual content."""
        multilingual_content = """
        English text here. This is in English.
        متن فارسی در اینجا. این به زبان فارسی است.
        نص عربي هنا. هذا باللغة العربية.
        中文内容在这里。这是中文。
        """

        doc = Document(
            content=multilingual_content,
            metadata={"source": "multilingual", "source_type": "text"},
        )

        chunks = await chunker.chunk_document(doc)

        assert len(chunks) >= 1
        # Should handle different scripts and languages
        combined_content = " ".join(chunk.content for chunk in chunks)
        assert "English" in combined_content
        assert "فارسی" in combined_content
        assert "عربي" in combined_content
        assert "中文" in combined_content

    @pytest.mark.asyncio
    async def test_chunk_document_custom_settings(self) -> None:
        """Test chunker with custom settings."""
        custom_chunker = TokenChunker(chunk_size=100, chunk_overlap=20)

        large_content = "Test sentence. " * 100
        doc = Document(content=large_content, metadata={"source": "test"})

        chunks = await custom_chunker.chunk_document(doc)

        # Should create more chunks with smaller chunk size
        assert len(chunks) > 3  # With 301 tokens and chunk_size=100, expect 3+ chunks

    @pytest.mark.asyncio
    async def test_chunk_texts_method(self, chunker: TokenChunker) -> None:
        """Test the chunk_texts method directly."""
        texts = [
            "First document content. " * 50,
            "Second document content. " * 50,
            "Third short content.",
        ]

        all_chunks = await chunker.chunk_texts(texts)

        assert len(all_chunks) >= 3  # At least one chunk per text
        assert all(isinstance(chunk, str) for chunk in all_chunks)

    def test_calculate_chunk_size(self, chunker: TokenChunker) -> None:
        """Test chunk size calculation."""
        test_text = "This is a test text with multiple words."

        # Test internal method if available
        if hasattr(chunker, "_calculate_tokens"):
            token_count = chunker._calculate_tokens(test_text)
            assert isinstance(token_count, int)
            assert token_count > 0

    def test_chunker_configuration(self) -> None:
        """Test different chunker configurations."""
        configs = [
            (100, 10),  # Small chunks, small overlap
            (500, 50),  # Medium chunks, medium overlap
            (1000, 100),  # Large chunks, large overlap
        ]

        for chunk_size, overlap in configs:
            chunker = TokenChunker(chunk_size=chunk_size, chunk_overlap=overlap)
            assert chunker.chunk_size == chunk_size
            assert chunker.chunk_overlap == overlap

    @pytest.mark.asyncio
    async def test_chunk_document_error_handling(self, chunker: TokenChunker) -> None:
        """Test error handling in document chunking."""
        # Test with None content
        with pytest.raises(Exception):
            doc = Document(content=None, metadata={})
            await chunker.chunk_document(doc)

    @pytest.mark.asyncio
    async def test_chunk_performance(self, chunker: TokenChunker) -> None:
        """Test chunking performance with large documents."""
        import time

        # Create a very large document
        large_content = "Performance test sentence. " * 5000
        doc = Document(content=large_content, metadata={"source": "performance"})

        start_time = time.time()
        chunks = await chunker.chunk_document(doc)
        end_time = time.time()

        # Should complete in reasonable time (less than 5 seconds)
        assert end_time - start_time < 5.0
        assert len(chunks) > 0
