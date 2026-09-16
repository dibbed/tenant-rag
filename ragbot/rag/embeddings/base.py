"""
Base embedder interface for text embedding generation.

This module defines the base interface that all embedding providers must implement,
providing a consistent API for generating embeddings from text.

Design goals:
- Consistent async and sync APIs
- Optional hooks for metrics and caching
- Lightweight preprocessing
"""

import math
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

# Precompiled whitespace regex for faster preprocessing
_WS_RE = re.compile(r"\s+")


class BaseEmbedder(ABC):
    """
    Abstract base class for text embedding generators.

    All embedding providers must inherit from this class and implement
    the embed methods to provide consistent embedding generation interface.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the embedder with configuration options.

        Args:
            **kwargs: Embedder-specific configuration options
        """
        self.config = kwargs
        self.model_name = kwargs.get("model_name", "default")
        self.batch_size = kwargs.get("batch_size", 100)
        self.max_retries = kwargs.get("max_retries", 3)
        self.timeout = kwargs.get("timeout", 30.0)

    @abstractmethod
    async def embed_texts(self, texts: List[str], **kwargs: Any) -> List[List[float]]:
        """
        Generate embeddings for a list of texts asynchronously.

        Args:
            texts: List of texts to embed
            **kwargs: Additional embedding options

        Returns:
            List[List[float]]: List of embedding vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        pass

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

    @abstractmethod
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
        pass

    async def embed_single(self, text: str, **kwargs: Any) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            **kwargs: Additional embedding options

        Returns:
            List[float]: Embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        embeddings = await self.embed_texts([text], **kwargs)
        return embeddings[0]

    def embed_single_sync(self, text: str, **kwargs: Any) -> List[float]:
        """
        Generate embedding for a single text synchronously.

        Args:
            text: Text to embed
            **kwargs: Additional embedding options

        Returns:
            List[float]: Embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        embeddings = self.embed_texts_sync([text], **kwargs)
        return embeddings[0] if embeddings else []

    async def embed_batch(
        self, texts: List[str], batch_size: Optional[int] = None, **kwargs: Any
    ) -> List[List[float]]:
        """
        Generate embeddings for texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Batch size override
            **kwargs: Additional embedding options

        Returns:
            List[List[float]]: List of embedding vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not texts:
            return []

        batch_size = batch_size or self.batch_size
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_embeddings = await self.embed_texts(batch_texts, **kwargs)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this embedder.

        Returns:
            int: Embedding dimension
        """
        # Default implementation - subclasses should override
        return 768

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the embedding model.

        Returns:
            Dict[str, Any]: Model information
        """
        return {
            "provider": self.__class__.__name__,
            "model_name": self.model_name,
            "embedding_dimension": self.get_embedding_dimension(),
            "batch_size": self.batch_size,
            "config": self.config,
        }

    def validate_texts(self, texts: List[str]) -> bool:
        """
        Validate input texts for embedding.

        Args:
            texts: List of texts to validate

        Returns:
            bool: True if texts are valid, False otherwise
        """
        if not isinstance(texts, list):
            return False

        if not texts:
            return False

        for text in texts:
            if not isinstance(text, str):
                return False
            if not text.strip():
                return False

        return True

    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text before embedding.

        Args:
            text: Text to preprocess

        Returns:
            str: Preprocessed text
        """
        # Default preprocessing - subclasses can override
        # Strip whitespace and collapse multiple spaces to single space
        preprocessed = text.strip()
        preprocessed = _WS_RE.sub(" ", preprocessed)
        return preprocessed

    def postprocess_embedding(self, embedding: List[float]) -> List[float]:
        """
        Postprocess embedding after generation.

        Args:
            embedding: Raw embedding vector

        Returns:
            List[float]: Processed embedding vector
        """
        # Default postprocessing - subclasses can override
        return embedding

    def normalize_embedding(self, embedding: List[float]) -> List[float]:
        """
        Normalize embedding vector to unit length.

        Args:
            embedding: Embedding vector to normalize

        Returns:
            List[float]: Normalized embedding vector
        """
        try:
            # Pure-python path for small vectors to reduce overhead
            if len(embedding) <= 64:
                sq_sum = sum(v * v for v in embedding)
                if sq_sum <= 0.0:
                    return embedding
                inv = 1.0 / math.sqrt(sq_sum)
                return [v * inv for v in embedding]

            embedding_array = np.array(embedding)
            norm = np.linalg.norm(embedding_array)
            if norm == 0:
                return embedding
            normalized = embedding_array / norm
            return normalized.tolist()

        except Exception:
            # Return original embedding if normalization fails
            return embedding

    def compute_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            float: Cosine similarity score (-1 to 1)
        """
        try:
            # Pure-python path for small vectors
            if len(embedding1) == len(embedding2) and len(embedding1) <= 64:
                dot = 0.0
                n1 = 0.0
                n2 = 0.0
                for a, b in zip(embedding1, embedding2):
                    dot += a * b
                    n1 += a * a
                    n2 += b * b
                if n1 <= 0.0 or n2 <= 0.0:
                    return 0.0
                return float(dot / (math.sqrt(n1) * math.sqrt(n2)))

            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(dot_product / (norm1 * norm2))

        except Exception:
            return 0.0

    def get_cache_key(self, text: str, **kwargs: Any) -> str:
        """
        Generate cache key for text embedding.

        Args:
            text: Text to generate key for
            **kwargs: Additional parameters that affect embedding

        Returns:
            str: Cache key
        """
        import hashlib

        # Include model name and relevant config in cache key
        key_components = [self.model_name, text, str(sorted(kwargs.items()))]

        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()

    # Optional cache hooks (no-op by default)
    async def get_cached_embedding(
        self, text: str, **_kwargs: Any
    ) -> Optional[List[float]]:
        """Optional hook: retrieve cached embedding for a text (override in subclasses)."""
        return None

    async def set_cached_embedding(
        self, text: str, embedding: List[float], **_kwargs: Any
    ) -> None:
        """Optional hook: store embedding for a text in cache (override in subclasses)."""
        return None

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the embedding service.

        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            # Test with a simple text
            test_text = "Health check test"
            embedding = await self.embed_single(test_text)

            return {
                "status": "healthy",
                "model_name": self.model_name,
                "embedding_dimension": len(embedding),
                "test_successful": True,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "model_name": self.model_name,
                "error": str(e),
                "test_successful": False,
            }

    # Optional metric hooks (no-op by default)
    def _on_embed_start(self, texts: List[str], **_kwargs: Any) -> None:
        """Hook called before embedding starts (override in subclasses)."""
        return None

    def _on_embed_end(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        duration: float,
        **_kwargs: Any,
    ) -> None:
        """Hook called after embedding ends (override in subclasses)."""
        return None


# For backward compatibility
Embedder = BaseEmbedder
