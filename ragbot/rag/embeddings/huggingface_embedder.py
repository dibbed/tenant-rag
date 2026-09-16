"""
HuggingFace embedding provider implementation.

This module provides HuggingFace-based text embedding generation using
sentence-transformers library for local embedding generation.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import torch
    from sentence_transformers import SentenceTransformer

    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False

from ragbot.caching import cache_manager
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager
from ragbot.rag.embeddings.base import BaseEmbedder
from ragbot.rag.exceptions import EmbeddingError


class HuggingFaceEmbedder(BaseEmbedder):
    """
    HuggingFace embedding provider implementation.

    This embedder uses HuggingFace sentence-transformers to generate
    embeddings locally without requiring API calls.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize HuggingFace embedder.

        Args:
            **kwargs: Configuration options including:
                - model_name: HuggingFace model name
                - device: Device to run model on ('cpu', 'cuda', 'auto')
                - normalize_embeddings: Whether to normalize embeddings
                - batch_size: Batch size for processing
                - cache_folder: Cache folder for model downloads
        """
        super().__init__(**kwargs)

        if not HUGGINGFACE_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for HuggingFace embeddings. "
                "Install with: pip install sentence-transformers"
            )

        # Resolve configuration with settings as defaults
        default_model = getattr(settings.embedding, "model", "all-MiniLM-L6-v2")
        self.model_name = kwargs.get("model_name", default_model)
        self.device = kwargs.get("device", "auto")
        self.normalize_embeddings = kwargs.get("normalize_embeddings", True)
        # Default local cache folder to ensure reuse across runs
        self.cache_folder = kwargs.get("cache_folder", "./cache/sentence_transformers")
        # Ensure batch_size and timeout follow embedding settings when not provided
        self.batch_size = kwargs.get(
            "batch_size", getattr(settings.embedding, "batch_size", self.batch_size)
        )
        self.timeout = kwargs.get(
            "timeout", getattr(settings.embedding, "timeout", self.timeout)
        )

        # Resolve 'auto' device to actual device
        if self.device == "auto":
            if torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"

        # Initialize model
        self.model: Optional[SentenceTransformer] = None
        self._load_model()

        logger.info(
            "HuggingFace embedder initialized",
            model=self.model_name,
            device=self.device,
            dimension=self.get_embedding_dimension(),
        )

    def _load_model(self) -> None:
        """Load the sentence transformer model."""
        try:
            logger.info(f"Loading HuggingFace model: {self.model_name}")

            self.model = SentenceTransformer(
                self.model_name, device=self.device, cache_folder=self.cache_folder
            )

            # Set model to evaluation mode
            self.model.eval()

            logger.info(
                "Model loaded successfully",
                model=self.model_name,
                device=str(self.model.device),
                max_seq_length=self.model.max_seq_length,
            )

        except Exception as e:
            logger.error(f"Failed to load HuggingFace model: {e}")
            raise EmbeddingError(
                f"Failed to load model {self.model_name}: {str(e)}",
                provider="huggingface",
                model=self.model_name,
                details=str(e),
            ) from e

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings for the current model."""
        if self.model is None:
            # Default dimensions for common models
            model_dims = {
                "all-MiniLM-L6-v2": 384,
                "all-MiniLM-L12-v2": 384,
                "all-mpnet-base-v2": 768,
                "all-distilroberta-v1": 768,
                "paraphrase-MiniLM-L6-v2": 384,
                "paraphrase-mpnet-base-v2": 768,
            }
            return model_dims.get(self.model_name, 768)

        return self.model.get_sentence_embedding_dimension()

    async def embed_texts(self, texts: List[str], **kwargs: Any) -> List[List[float]]:
        """
        Generate embeddings for a list of texts asynchronously.

        Args:
            texts: List of texts to embed
            **kwargs: Additional options:
                - show_progress_bar: Show progress bar during encoding
                - convert_to_numpy: Convert to numpy arrays
                - normalize_embeddings: Override normalization setting

        Returns:
            List[List[float]]: List of embedding vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not self.validate_texts(texts):
            raise EmbeddingError(
                "Invalid texts provided for embedding",
                provider="huggingface",
                model=self.model_name,
            )

        if self.model is None:
            raise EmbeddingError(
                "Model not loaded", provider="huggingface", model=self.model_name
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

            # Set encoding parameters
            encode_kwargs = {
                "show_progress_bar": kwargs.get("show_progress_bar", False),
                "convert_to_numpy": True,
                "normalize_embeddings": kwargs.get(
                    "normalize_embeddings", self.normalize_embeddings
                ),
                "batch_size": kwargs.get("batch_size", self.batch_size),
            }

            # Try cache first
            results: List[Optional[List[float]]] = [None] * len(processed_texts)
            to_compute_indices: List[int] = []
            to_compute_texts: List[str] = []

            for i, ptxt in enumerate(processed_texts):
                try:
                    cached = await cache_manager.get_cached_embedding(
                        ptxt, self.model_name
                    )
                    if cached is None:
                        cached = await self.get_cached_embedding(ptxt)
                except Exception:
                    cached = None
                if cached is not None:
                    results[i] = cached
                else:
                    to_compute_indices.append(i)
                    to_compute_texts.append(ptxt)

            new_embeddings: List[List[float]] = []
            if to_compute_texts:
                # Generate embeddings for uncached texts
                # Offload blocking encode to thread in async context
                new_embeddings = await asyncio.to_thread(
                    self.model.encode,
                    to_compute_texts,
                    **encode_kwargs,
                )
                if isinstance(new_embeddings, np.ndarray):
                    new_embeddings = new_embeddings.tolist()
                # Postprocess and assign
                for j, emb in enumerate(new_embeddings):
                    emb = self.postprocess_embedding(emb)
                    idx = to_compute_indices[j]
                    results[idx] = emb
                    try:
                        await cache_manager.cache_embedding(
                            processed_texts[idx], self.model_name, emb
                        )
                        await self.set_cached_embedding(processed_texts[idx], emb)
                    except Exception:
                        pass

            # Fill any remaining None with empty vectors (shouldn't happen)
            embeddings = [r if r is not None else [] for r in results]

            # Convert to list of lists
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()

            # Postprocess embeddings
            embeddings = [self.postprocess_embedding(emb) for emb in embeddings]

            # Record metrics
            duration = time.time() - start_time
            metrics_manager.record_query_processing(
                language="unknown", status="success", llm_duration=duration
            )

            # metrics hook end
            try:
                self._on_embed_end(texts, embeddings, duration, **kwargs)
            except Exception:
                pass

            logger.debug(
                f"Generated {len(embeddings)} embeddings",
                model=self.model_name,
                duration=duration,
                device=str(self.model.device),
            )

            return embeddings

        except Exception as e:
            metrics_manager.record_error("embedding_generation", "huggingface")
            logger.error(f"Error generating HuggingFace embeddings: {e}")

            if "out of memory" in str(e).lower():
                raise EmbeddingError(
                    f"GPU out of memory: {str(e)}",
                    provider="huggingface",
                    model=self.model_name,
                    details=str(e),
                ) from e
            else:
                raise EmbeddingError(
                    f"HuggingFace embedding generation failed: {str(e)}",
                    provider="huggingface",
                    model=self.model_name,
                    details=str(e),
                ) from e

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
        # Provide a true synchronous path without spawning an event loop
        if not self.validate_texts(texts):
            raise EmbeddingError(
                "Invalid texts provided for embedding",
                provider="huggingface",
                model=self.model_name,
            )
        if self.model is None:
            raise EmbeddingError(
                "Model not loaded",
                provider="huggingface",
                model=self.model_name,
            )
        try:
            start_time = time.time()
            try:
                self._on_embed_start(texts, **kwargs)
            except Exception:
                pass
            processed_texts = [self.preprocess_text(text) for text in texts]
            encode_kwargs = {
                "show_progress_bar": kwargs.get("show_progress_bar", False),
                "convert_to_numpy": True,
                "normalize_embeddings": kwargs.get(
                    "normalize_embeddings", self.normalize_embeddings
                ),
                "batch_size": kwargs.get("batch_size", self.batch_size),
            }
            embeddings = self.model.encode(processed_texts, **encode_kwargs)
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()
            embeddings = [self.postprocess_embedding(emb) for emb in embeddings]
            duration = time.time() - start_time
            try:
                metrics_manager.record_query_processing(
                    language="unknown",
                    status="success",
                    llm_duration=duration,
                )
            except Exception:
                pass
            logger.debug(
                f"Generated {len(embeddings)} embeddings (sync)",
                model=self.model_name,
                duration=duration,
                device=str(self.model.device) if self.model else "unknown",
            )
            try:
                self._on_embed_end(texts, embeddings, duration, **kwargs)
            except Exception:
                pass
            return embeddings
        except Exception as e:
            try:
                metrics_manager.record_error("embedding_generation", "huggingface")
            except Exception:
                pass
            raise EmbeddingError(
                f"HuggingFace embedding generation failed (sync): {str(e)}",
                provider="huggingface",
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

    def preprocess_text(self, text: str) -> str:
        """Preprocess text for HuggingFace embedding."""
        # Basic preprocessing
        text = text.strip()

        # Truncate if too long (most models have max sequence length)
        if self.model and hasattr(self.model, "max_seq_length"):
            max_length = self.model.max_seq_length
            # Rough estimation: 4 characters per token
            max_chars = max_length * 4
            if len(text) > max_chars:
                text = text[:max_chars]
                logger.debug(f"Truncated text to {max_chars} characters")

        return text

    def get_model_info(self) -> Dict[str, Any]:
        """Get detailed information about the model."""
        info = super().get_model_info()

        if self.model:
            info.update(
                {
                    "device": str(self.model.device),
                    "max_seq_length": getattr(self.model, "max_seq_length", "unknown"),
                    "normalize_embeddings": self.normalize_embeddings,
                    "model_loaded": True,
                }
            )
        else:
            info.update(
                {
                    "model_loaded": False,
                    "normalize_embeddings": self.normalize_embeddings,
                }
            )

        return info

    def get_device_info(self) -> Dict[str, Any]:
        """Get information about the device being used."""
        device_info = {
            "requested_device": self.device,
            "torch_available": HUGGINGFACE_AVAILABLE,
        }

        if HUGGINGFACE_AVAILABLE and torch.cuda.is_available():
            device_info.update(
                {
                    "cuda_available": True,
                    "cuda_device_count": torch.cuda.device_count(),
                    "current_device": torch.cuda.current_device()
                    if torch.cuda.is_available()
                    else None,
                }
            )
        else:
            device_info["cuda_available"] = False

        if self.model:
            device_info["actual_device"] = str(self.model.device)

        return device_info

    def clear_cache(self) -> None:
        """Clear model cache and free GPU memory."""
        if self.model and hasattr(self.model, "to"):
            # Move model to CPU to free GPU memory
            self.model.to("cpu")

        if HUGGINGFACE_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("Cleared CUDA cache")

    def reload_model(self, **kwargs: Any) -> None:
        """Reload the model with new parameters."""
        # Update configuration
        self.model_name = kwargs.get("model_name", self.model_name)
        self.device = kwargs.get("device", self.device)
        self.normalize_embeddings = kwargs.get(
            "normalize_embeddings", self.normalize_embeddings
        )

        # Clear existing model
        if self.model:
            del self.model
            self.model = None

        # Clear cache
        self.clear_cache()

        # Reload model
        self._load_model()

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on HuggingFace embedding service."""
        try:
            # Test with a simple text
            test_text = "Health check test for HuggingFace embeddings"
            embedding = await self.embed_single(test_text)

            device_info = self.get_device_info()

            return {
                "status": "healthy",
                "provider": "huggingface",
                "model_name": self.model_name,
                "embedding_dimension": len(embedding),
                "model_loaded": self.model is not None,
                "device_info": device_info,
                "test_successful": True,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "huggingface",
                "model_name": self.model_name,
                "model_loaded": self.model is not None,
                "error": str(e),
                "test_successful": False,
            }


class LocalEmbedder(HuggingFaceEmbedder):
    """Alias for HuggingFaceEmbedder for backward compatibility."""

    pass
