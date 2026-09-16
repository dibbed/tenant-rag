"""
OpenAI embeddings tests with proper mocking and error handling.

This module tests the OpenAI embeddings functionality with various scenarios
including API mocking, error handling, and edge cases.
"""

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ragbot.rag.embeddings.openai_embedder import OpenAIEmbedder
from ragbot.rag import EmbeddingError


class TestOpenAIEmbeddings:
    """Comprehensive test suite for OpenAI embeddings functionality."""

    @pytest.fixture
    def embedder(self) -> OpenAIEmbedder:
        """Create an OpenAIEmbedder instance for testing."""
        return OpenAIEmbedder(api_key="test-api-key")

    @pytest.fixture
    def mock_openai_response(self) -> dict:
        """Create a mock OpenAI API response."""
        return {
            "data": [
                {
                    "embedding": [0.1] * 1536,  # Standard OpenAI embedding dimension
                    "index": 0,
                },
                {"embedding": [0.2] * 1536, "index": 1},
            ],
            "model": "text-embedding-ada-002",
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        }

    @pytest.mark.asyncio
    async def test_embed_single_text(
        self, embedder: OpenAIEmbedder, mock_openai_response: dict
    ) -> None:
        """Test embedding a single text."""
        with patch.object(embedder, "async_client") as mock_client:
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
            )

            text = "This is a test text for embedding."
            embedding = await embedder.embed_text(text)

            assert isinstance(embedding, list)
            assert len(embedding) == 1536  # OpenAI standard dimension
            assert all(isinstance(x, float) for x in embedding)

            # Verify API was called correctly
            mock_client.embeddings.create.assert_called_once()
            call_args = mock_client.embeddings.create.call_args
            assert call_args[1]["input"] == [text]

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(
        self, embedder: OpenAIEmbedder, mock_openai_response: dict
    ) -> None:
        """Test embedding multiple texts."""
        texts = [
            "First text to embed.",
            "Second text to embed.",
            "متن فارسی برای تست embedding",
        ]

        with patch.object(embedder, "async_client") as mock_client:
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[0.1] * 1536),
                MagicMock(embedding=[0.2] * 1536),
                MagicMock(embedding=[0.3] * 1536),
            ]
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)

            embeddings = await embedder.embed_texts(texts)

            assert isinstance(embeddings, list)
            assert len(embeddings) == 3
            assert all(len(emb) == 1536 for emb in embeddings)
            assert all(isinstance(emb, list) for emb in embeddings)

            # Verify all embeddings are different (basic sanity check)
            assert embeddings[0] != embeddings[1]
            assert embeddings[1] != embeddings[2]

    @pytest.mark.asyncio
    async def test_embed_empty_text(self, embedder: OpenAIEmbedder) -> None:
        """Test handling of empty text."""
        with pytest.raises(
            EmbeddingError, match="Invalid texts provided for embedding"
        ):
            await embedder.embed_text("")

    @pytest.mark.asyncio
    async def test_embed_empty_list(self, embedder: OpenAIEmbedder) -> None:
        """Test handling of empty text list."""
        with pytest.raises(
            EmbeddingError, match="Invalid texts provided for embedding"
        ):
            await embedder.embed_texts([])

    @pytest.mark.asyncio
    async def test_embed_none_text(self, embedder: OpenAIEmbedder) -> None:
        """Test handling of None text."""
        with pytest.raises(EmbeddingError):
            await embedder.embed_text(None)

    @pytest.mark.asyncio
    async def test_embed_very_long_text(self, embedder: OpenAIEmbedder) -> None:
        """Test embedding very long text."""
        # Create text longer than typical token limits
        long_text = "This is a very long text. " * 5000

        with patch.object(embedder, "async_client") as mock_client:
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
            )

            # Should handle long text gracefully (truncate or chunk)
            embedding = await embedder.embed_text(long_text)

            assert isinstance(embedding, list)
            assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_embed_multilingual_text(self, embedder: OpenAIEmbedder) -> None:
        """Test embedding multilingual text."""
        multilingual_texts = [
            "English text here",
            "متن فارسی در اینجا",
            "نص عربي هنا",
            "中文内容在这里",
            "Русский текст здесь",
        ]

        with patch.object(embedder, "async_client") as mock_client:
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[i * 0.1] * 1536)
                for i in range(len(multilingual_texts))
            ]
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)

            embeddings = await embedder.embed_texts(multilingual_texts)

            assert len(embeddings) == len(multilingual_texts)
            assert all(len(emb) == 1536 for emb in embeddings)

    @pytest.mark.asyncio
    async def test_api_key_validation(self) -> None:
        """Test API key validation."""
        # Test with empty API key
        with pytest.raises(EmbeddingError, match="OpenAI API key is required"):
            OpenAIEmbedder(api_key="")

        # Test with None API key
        with pytest.raises(EmbeddingError, match="OpenAI API key is required"):
            OpenAIEmbedder(api_key=None)

    @pytest.mark.asyncio
    async def test_api_error_handling(self, embedder: OpenAIEmbedder) -> None:
        """Test handling of API errors."""
        with patch.object(embedder, "async_client") as mock_client:
            # Simulate API error
            mock_client.embeddings.create = AsyncMock(
                side_effect=Exception("API Error occurred")
            )

            with pytest.raises(
                EmbeddingError, match="OpenAI embedding generation failed"
            ):
                await embedder.embed_text("Test text")

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, embedder: OpenAIEmbedder) -> None:
        """Test handling of rate limit errors."""
        with patch.object(embedder, "async_client") as mock_client:
            # Simulate rate limit error
            mock_client.embeddings.create = AsyncMock(
                side_effect=Exception("Rate limit exceeded")
            )

            with pytest.raises(EmbeddingError, match="OpenAI rate limit exceeded"):
                await embedder.embed_text("Test text")

    @pytest.mark.asyncio
    async def test_network_timeout(self, embedder: OpenAIEmbedder) -> None:
        """Test handling of network timeouts."""
        with patch.object(embedder, "async_client") as mock_client:
            mock_client.embeddings.create = AsyncMock(
                side_effect=Exception("Connection timeout")
            )

            with pytest.raises(
                EmbeddingError, match="OpenAI embedding generation failed"
            ):
                await embedder.embed_text("Test text")

    @pytest.mark.asyncio
    async def test_malformed_response(self, embedder: OpenAIEmbedder) -> None:
        """Test handling of malformed API responses."""
        with patch.object(embedder, "async_client") as mock_client:
            # Response missing embedding data
            mock_response = MagicMock()
            mock_response.data = []
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)

            # This should succeed but return empty list due to empty data
            embeddings = await embedder.embed_texts(["Test text"])
            assert embeddings == [None]  # Placeholder from empty response data

    @pytest.mark.asyncio
    async def test_batch_size_handling(self, embedder: OpenAIEmbedder) -> None:
        """Test handling of large batches."""
        # Create a large list of texts
        large_batch = [f"Text number {i}" for i in range(100)]

        with patch.object(embedder, "async_client") as mock_client:
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[i * 0.01] * 1536) for i in range(len(large_batch))
            ]
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)

            embeddings = await embedder.embed_texts(large_batch)

            assert len(embeddings) == 100
            # Should handle batching properly (OpenAI has limits on batch size)

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, embedder: OpenAIEmbedder) -> None:
        """Test that same text produces consistent embeddings."""
        test_text = "Consistent text for testing"

        with patch.object(embedder, "async_client") as mock_client:
            # Return consistent mock embedding
            mock_embedding = [0.5] * 1536
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(embedding=mock_embedding)])
            )

            embedding1 = await embedder.embed_text(test_text)
            embedding2 = await embedder.embed_text(test_text)

            assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_custom_model_configuration(self) -> None:
        """Test embedder with custom model configuration."""
        custom_embedder = OpenAIEmbedder(
            api_key="test-key", model_name="text-embedding-3-large"
        )

        with patch.object(custom_embedder, "async_client") as mock_client:
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 3072)])
            )

            embedding = await custom_embedder.embed_text("Test text")

            assert len(embedding) == 3072

            # Verify model parameter was used
            call_args = mock_client.embeddings.create.call_args
            assert call_args[1]["model"] == "text-embedding-3-large"

    @pytest.mark.asyncio
    async def test_embedding_normalization(self, embedder: OpenAIEmbedder) -> None:
        """Test embedding normalization if implemented."""
        with patch.object(embedder, "async_client") as mock_client:
            # Create embedding with large values
            unnormalized_embedding = [10.0] * 1536
            mock_client.embeddings.create = AsyncMock(
                return_value=MagicMock(
                    data=[MagicMock(embedding=unnormalized_embedding)]
                )
            )

            embedding = await embedder.embed_text("Test text")

            # Check if normalization is applied (implementation-dependent)
            if (
                hasattr(embedder, "normalize_embeddings")
                and embedder.normalize_embeddings
            ):
                import math

                magnitude = math.sqrt(sum(x * x for x in embedding))
                assert abs(magnitude - 1.0) < 0.001  # Should be unit vector
            else:
                assert embedding == unnormalized_embedding

    @pytest.mark.asyncio
    async def test_concurrent_embedding_requests(
        self, embedder: OpenAIEmbedder
    ) -> None:
        """Test handling of concurrent embedding requests."""
        texts = [f"Concurrent text {i}" for i in range(10)]

        with patch.object(embedder, "async_client") as mock_client:
            mock_response = MagicMock()
            mock_response.data = [
                MagicMock(embedding=[i * 0.1] * 1536) for i in range(len(texts))
            ]
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)

            # Run concurrent embedding requests
            tasks = [embedder.embed_text(text) for text in texts]
            embeddings = await asyncio.gather(*tasks)

            assert len(embeddings) == 10
            assert all(len(emb) == 1536 for emb in embeddings)

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, embedder: OpenAIEmbedder) -> None:
        """Test memory efficiency with large embeddings."""
        with patch.object(embedder, "async_client") as mock_client:
            # Simulate large embedding response
            large_embedding = [0.001] * 1536
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=large_embedding)] * 50
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)

            # Process many texts to test memory usage
            many_texts = [f"Text {i}" for i in range(50)]
            embeddings = await embedder.embed_texts(many_texts)

            # Should complete without memory errors
            assert len(embeddings) == 50
            assert all(isinstance(emb, list) for emb in embeddings)
