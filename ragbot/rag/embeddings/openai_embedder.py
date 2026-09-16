"""
OpenAI embedding provider implementation.

This module provides OpenAI-based text embedding generation using the OpenAI API
with proper error handling, rate limiting, and caching support.
"""

import asyncio
import time
from typing import Any, Dict, List

try:
    from openai import AsyncOpenAI, OpenAI
    from openai.types import CreateEmbeddingResponse

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

    # Create dummy types and clients for when OpenAI is not available (tests patch these)
    class CreateEmbeddingResponse:  # type: ignore
        pass

    class AsyncOpenAI:  # type: ignore
        def __init__(self, *_, **__):
            pass

    class OpenAI:  # type: ignore
        def __init__(self, *_, **__):
            pass


# from ragbot.caching import cache_manager  # Lazy import to avoid circular dependency
# Note: caching in sync path is intentionally skipped to avoid async calls
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager
from ragbot.rag.embeddings.base import BaseEmbedder
from ragbot.rag.exceptions import EmbeddingError


class OpenAIEmbedder(BaseEmbedder):
    """
    OpenAI embedding provider implementation.

    This embedder uses OpenAI's embedding API to generate high-quality
    text embeddings with support for various OpenAI embedding models.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize OpenAI embedder.

        Args:
            **kwargs: Configuration options including:
                - api_key: OpenAI API key
                - model_name: OpenAI embedding model name
                - batch_size: Batch size for API requests
                - max_retries: Maximum number of retries
                - timeout: Request timeout in seconds
                - rate_limit_rpm: Rate limit in requests per minute
        """
        super().__init__(**kwargs)

        # Allow operation in test environments without the openai package; tests patch clients

        self.api_key = kwargs.get("api_key", settings.openai_api_key)
        self.model_name = kwargs.get("model_name", settings.embedding.model)
        self.batch_size = kwargs.get("batch_size", settings.embedding.batch_size)
        self.timeout = kwargs.get("timeout", settings.embedding.timeout)
        self.rate_limit_rpm = kwargs.get("rate_limit_rpm", 3000)  # OpenAI default

        if not self.api_key:
            raise EmbeddingError(
                "OpenAI API key is required", provider="openai", model=self.model_name
            )

        # Initialize OpenAI clients
        self.client = OpenAI(api_key=self.api_key, timeout=self.timeout)
        self.async_client = AsyncOpenAI(api_key=self.api_key, timeout=self.timeout)

        # Rate limiting
        self.last_request_time = 0
        self.request_interval = 60.0 / self.rate_limit_rpm  # Seconds between requests

        # Model-specific configurations
        self.model_configs = {
            "text-embedding-ada-002": {"dimension": 1536, "max_tokens": 8191},
            "text-embedding-3-small": {"dimension": 1536, "max_tokens": 8191},
            "text-embedding-3-large": {"dimension": 3072, "max_tokens": 8191},
        }

        logger.info(
            "OpenAI embedder initialized",
            model=self.model_name,
            batch_size=self.batch_size,
            dimension=self.get_embedding_dimension(),
        )

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings for the current model."""
        return self.model_configs.get(self.model_name, {}).get("dimension", 1536)

    def get_max_tokens(self) -> int:
        """Get the maximum token limit for the current model."""
        return self.model_configs.get(self.model_name, {}).get("max_tokens", 8191)

    async def embed_texts(self, texts: List[str], **kwargs: Any) -> List[List[float]]:
        """
        Generate embeddings for a list of texts asynchronously.

        Args:
            texts: List of texts to embed
            **kwargs: Additional options:
                - model: Override model name
                - dimensions: Override embedding dimensions (for newer models)

        Returns:
            List[List[float]]: List of embedding vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not self.validate_texts(texts):
            raise EmbeddingError(
                "Invalid texts provided for embedding",
                provider="openai",
                model=self.model_name,
            )

        try:
            start_time = time.time()
            model = kwargs.get("model", self.model_name)

            # metrics hook
            try:
                self._on_embed_start(texts, **kwargs)
            except Exception:
                pass

            # Check cache for each text
            embeddings = []
            texts_to_embed = []
            cache_keys = []
            cache_indices = []

            for i, text in enumerate(texts):
                processed_text = self.preprocess_text(text)
                from ragbot.caching import cache_manager

                cached_embedding = await cache_manager.get_cached_embedding(
                    processed_text, model
                )

                if cached_embedding is not None:
                    embeddings.append(cached_embedding)
                    logger.debug(f"Using cached embedding for text {i}")
                else:
                    # Need to generate embedding
                    texts_to_embed.append(processed_text)
                    cache_keys.append(processed_text)
                    cache_indices.append(i)
                    embeddings.append(None)  # Placeholder

            # Generate embeddings for uncached texts
            response = None  # Initialize response variable
            if texts_to_embed:
                # Apply rate limiting
                await self._apply_rate_limit()

                # Prepare request parameters
                request_params = {
                    "input": texts_to_embed,
                    "model": model,
                }

                # Add dimensions parameter for newer models
                if "dimensions" in kwargs and model in [
                    "text-embedding-3-small",
                    "text-embedding-3-large",
                ]:
                    request_params["dimensions"] = kwargs["dimensions"]

                # Make API request with retries
                response = await self._make_request_with_retries(request_params)

                # Extract and postprocess embeddings
                new_embeddings = [
                    self.postprocess_embedding(data.embedding) for data in response.data
                ]

                # Cache new embeddings and fill in placeholders
                for i, (cache_key, embedding) in enumerate(
                    zip(cache_keys, new_embeddings)
                ):
                    # Cache the embedding
                    await cache_manager.cache_embedding(cache_key, model, embedding)

                    # Fill in the placeholder
                    original_index = cache_indices[i]
                    embeddings[original_index] = embedding

                logger.debug(
                    f"Generated and cached {len(new_embeddings)} new embeddings"
                )
            else:
                logger.debug("All embeddings found in cache")

            # Record metrics
            duration = time.time() - start_time
            metrics_manager.record_query_processing(
                language="unknown", status="success", llm_duration=duration
            )

            logger.debug(
                f"Generated {len(embeddings)} embeddings",
                model=model,
                duration=duration,
                total_tokens=response.usage.total_tokens
                if response and response.usage
                else 0,
            )

            # metrics hook end
            try:
                self._on_embed_end(texts, embeddings, duration, **kwargs)
            except Exception:
                pass

            return embeddings

        except Exception as e:
            metrics_manager.record_error("embedding_generation", "openai")
            logger.error(f"Error generating OpenAI embeddings: {e}")

            if "rate limit" in str(e).lower():
                raise EmbeddingError(
                    f"OpenAI rate limit exceeded: {str(e)}",
                    provider="openai",
                    model=self.model_name,
                    details=str(e),
                ) from e
            elif "invalid" in str(e).lower():
                raise EmbeddingError(
                    f"Invalid request to OpenAI: {str(e)}",
                    provider="openai",
                    model=self.model_name,
                    details=str(e),
                ) from e
            else:
                raise EmbeddingError(
                    f"OpenAI embedding generation failed: {str(e)}",
                    provider="openai",
                    model=self.model_name,
                    details=str(e),
                ) from e

    async def embed_text(self, text: str, **kwargs: Any) -> List[float]:
        """
        Generate embedding for a single text (compatibility method).

        Args:
            text: Text to embed
            **kwargs: Additional embedding options

        Returns:
            List[float]: Embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        embeddings = await self.embed_texts([text], **kwargs)
        return embeddings[0] if embeddings else []

    def embed_texts_sync(self, texts: List[str], **kwargs: Any) -> List[List[float]]:
        """
        Generate embeddings for a list of texts synchronously.

        Args:
            texts: List of texts to embed
            **kwargs: Additional embedding options

        Returns:
            List[List[float]]: List of embedding vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not self.validate_texts(texts):
            raise EmbeddingError(
                "Invalid texts provided for embedding",
                provider="openai",
                model=self.model_name,
            )

        try:
            start_time = time.time()

            # metrics hook
            try:
                self._on_embed_start(texts, **kwargs)
            except Exception:
                pass

            # Preprocess texts
            processed_texts = [self.preprocess_text(text) for text in texts]

            model = kwargs.get("model", self.model_name)

            # Sync path: perform direct request without cache (async cache is not available here)
            self._apply_rate_limit_sync()

            request_params = {
                "input": processed_texts,
                "model": model,
            }
            if "dimensions" in kwargs and model in [
                "text-embedding-3-small",
                "text-embedding-3-large",
            ]:
                request_params["dimensions"] = kwargs["dimensions"]

            response = self._make_request_with_retries_sync(request_params)
            out = [data.embedding for data in response.data]
            out = [self.postprocess_embedding(emb) for emb in out]

            duration = time.time() - start_time
            metrics_manager.record_query_processing(
                language="unknown", status="success", llm_duration=duration
            )
            try:
                self._on_embed_end(texts, out, duration, **kwargs)
            except Exception:
                pass

            logger.debug(
                f"Generated {len(out)} embeddings (sync)",
                model=model,
                duration=duration,
                total_tokens=(
                    response.usage.total_tokens
                    if getattr(response, "usage", None)
                    else 0
                ),
            )

            return out

        except Exception as e:
            metrics_manager.record_error("embedding_generation", "openai")
            logger.error(f"Error generating OpenAI embeddings (sync): {e}")

            if "rate limit" in str(e).lower():
                raise EmbeddingError(
                    f"OpenAI rate limit exceeded: {str(e)}",
                    provider="openai",
                    model=self.model_name,
                    details=str(e),
                ) from e
            else:
                raise EmbeddingError(
                    f"OpenAI embedding generation failed: {str(e)}",
                    provider="openai",
                    model=self.model_name,
                    details=str(e),
                ) from e

    async def _make_request_with_retries(
        self, request_params: Dict[str, Any]
    ) -> CreateEmbeddingResponse:
        """Make API request with retry logic."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = await self.async_client.embeddings.create(**request_params)
                return response

            except Exception as e:
                last_exception = e

                # Check if we should retry
                if attempt < self.max_retries - 1:
                    if "rate limit" in str(e).lower():
                        # Exponential backoff for rate limits
                        wait_time = (2**attempt) * 1.0
                        logger.warning(
                            f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    elif "timeout" in str(e).lower() or "connection" in str(e).lower():
                        # Retry on timeout/connection errors
                        wait_time = (2**attempt) * 0.5
                        logger.warning(
                            f"Connection error, waiting {wait_time}s before retry {attempt + 1}"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                # Don't retry on other errors
                break

        # All retries failed
        raise last_exception

    def _make_request_with_retries_sync(
        self, request_params: Dict[str, Any]
    ) -> CreateEmbeddingResponse:
        """Make API request with retry logic (synchronous)."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = self.client.embeddings.create(**request_params)
                return response

            except Exception as e:
                last_exception = e

                # Check if we should retry
                if attempt < self.max_retries - 1:
                    if "rate limit" in str(e).lower():
                        # Exponential backoff for rate limits
                        wait_time = (2**attempt) * 1.0
                        logger.warning(
                            f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}"
                        )
                        time.sleep(wait_time)
                        continue
                    elif "timeout" in str(e).lower() or "connection" in str(e).lower():
                        # Retry on timeout/connection errors
                        wait_time = (2**attempt) * 0.5
                        logger.warning(
                            f"Connection error, waiting {wait_time}s before retry {attempt + 1}"
                        )
                        time.sleep(wait_time)
                        continue

                # Don't retry on other errors
                break

        # All retries failed
        raise last_exception

    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting for API requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    def _apply_rate_limit_sync(self) -> None:
        """Apply rate limiting for API requests (synchronous)."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def preprocess_text(self, text: str) -> str:
        """Preprocess text for OpenAI embedding."""
        # Basic preprocessing
        text = text.strip()

        # Replace newlines with spaces for better embedding quality
        text = text.replace("\n", " ").replace("\r", " ")

        # Remove excessive whitespace
        import re

        text = re.sub(r"\s+", " ", text)

        return text

    def postprocess_embedding(self, embedding: List[float]) -> List[float]:
        """Postprocess OpenAI embedding."""
        # OpenAI embeddings are already normalized, but we can add custom processing here
        return embedding

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on OpenAI embedding service."""
        try:
            # Test with a simple text
            test_text = "Health check test for OpenAI embeddings"
            embedding = await self.embed_single(test_text)

            return {
                "status": "healthy",
                "provider": "openai",
                "model_name": self.model_name,
                "embedding_dimension": len(embedding),
                "api_key_configured": bool(self.api_key),
                "test_successful": True,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "openai",
                "model_name": self.model_name,
                "api_key_configured": bool(self.api_key),
                "error": str(e),
                "test_successful": False,
            }
