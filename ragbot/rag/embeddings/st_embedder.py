"""
Local embedding provider using SentenceTransformers (Hugging Face).

This embedder produces embeddings fully offline once the model is cached.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.embeddings.base import BaseEmbedder
from ragbot.rag.exceptions import EmbeddingError

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class STEmbedder(BaseEmbedder):
    """SentenceTransformers-based embedder (offline capable)."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.model_name = model_name
        self.device = device or "auto"
        self._model: SentenceTransformer | None = None
        self._cache: dict[str, list[float]] = {}

        logger.info(
            "STEmbedder initialized",
            model=self.model_name,
            device=self.device,
        )

    def _load(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            # trust_remote_code not needed for sentence-transformers
            cache_dir = getattr(
                getattr(settings, "embedding", object()),
                "cache_folder",
                "./cache/sentence_transformers",
            )
            device = self.device
            if device == "auto":
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = SentenceTransformer(
                self.model_name,
                device=device,
                cache_folder=cache_dir,  # Cache models locally (configurable)
            )

    async def embed_texts(
        self, texts: list[str], **kwargs: Any
    ) -> list[list[float]]:
        import asyncio
        import hashlib

        self._load()
        model = self._model
        assert model is not None

        # Check cache first
        cached_results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
            if text_hash in self._cache:
                cached_results.append((i, self._cache[text_hash]))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Generate embeddings for uncached texts
        if uncached_texts:

            def _encode() -> list[list[float]]:
                vectors = model.encode(
                    uncached_texts,
                    normalize_embeddings=False,
                    show_progress_bar=False,
                    batch_size=32,  # Optimize batch size
                    convert_to_numpy=True,
                )
                return [v.tolist() for v in vectors]

            new_embeddings = await asyncio.to_thread(_encode)

            # Cache new embeddings
            for i, (text, embedding) in enumerate(zip(uncached_texts, new_embeddings, strict=False)):
                text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
                self._cache[text_hash] = embedding
                cached_results.append((uncached_indices[i], embedding))

        # Sort results by original order
        cached_results.sort(key=lambda x: x[0])
        return [result[1] for result in cached_results]

    async def embed_single(self, text: str, **kwargs: Any) -> list[float]:
        res = await self.embed_texts([text], **kwargs)
        return res[0] if res else []

    def embed_texts_sync(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        """Synchronous embedding generation."""
        try:
            self._load()
            model = self._model
            assert model is not None

            # Check cache first
            cached_results = []
            uncached_texts = []
            uncached_indices = []

            for i, text in enumerate(texts):
                text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
                if text_hash in self._cache:
                    cached_results.append((i, self._cache[text_hash]))
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)

            # Generate embeddings for uncached texts
            if uncached_texts:
                vectors = model.encode(
                    uncached_texts,
                    normalize_embeddings=False,
                    show_progress_bar=False,
                    batch_size=32,
                    convert_to_numpy=True,
                )
                new_embeddings = [v.tolist() for v in vectors]

                # Cache new embeddings
                for i, (text, embedding) in enumerate(
                    zip(uncached_texts, new_embeddings, strict=False)
                ):
                    text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
                    self._cache[text_hash] = embedding
                    cached_results.append((uncached_indices[i], embedding))

            # Sort results by original order
            cached_results.sort(key=lambda x: x[0])
            return [result[1] for result in cached_results]

        except Exception as e:
            raise EmbeddingError(
                f"Failed to generate embeddings: {e}",
                provider="sentence_transformers",
                model=self.model_name,
            ) from e

    def get_embedding_dimension(self) -> int:
        """Get embedding dimension for the model."""
        try:
            self._load()
            model = self._model
            assert model is not None
            dimension = model.get_sentence_embedding_dimension()
            if dimension is not None:
                return int(dimension)
        except Exception:
            pass

        # Fallback dimensions for common models
        try:
            dimension_map = {
                "all-MiniLM-L6-v2": 384,
                "all-MiniLM-L12-v2": 384,
                "all-mpnet-base-v2": 768,
                "paraphrase-multilingual-MiniLM-L12-v2": 384,
            }
            return dimension_map.get(self.model_name.split("/")[-1], 384)
        except Exception:
            return 384
