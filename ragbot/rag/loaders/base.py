"""
Base loader interface for document loading.

This module defines the base interface that all document loaders must implement,
providing a consistent API for loading different types of documents.

Notes:
- Downstream chunkers/optimizers rely on precise spans (start/end) and page-level
  information when available. Loaders should, at minimum, populate these in the
  `metadata` dictionary with conventional keys:
  - metadata['source_type']: str (e.g., 'pdf', 'html', 'docx', 'text')
  - metadata['page']: Optional[int]
  - metadata['span']: Optional[dict] with keys {'start': int, 'end': int}
  - metadata['language']: Optional[str]
  - metadata['mime_type']: Optional[str]
- Keep the `Document` dataclass minimal to avoid breaking existing call sites.
  Prefer enriching `metadata` with the standardized keys above.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


class Document:
    """
    Represents a loaded document with metadata.

    Attributes:
        text: The text content of the document
        metadata: Additional metadata about the document
        source: Source identifier (file path, URL, etc.)
        document_type: Type of document (pdf, url, text, etc.)
    """

    text: str
    metadata: Dict[str, Any]
    source: Optional[str]
    document_type: Optional[str]

    def __init__(
        self,
        text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        document_type: Optional[str] = None,
        *,
        content: Optional[str] = None,
    ) -> None:
        """Initialize Document supporting both text and legacy content kwargs."""
        self.text = text if text is not None else content
        self.metadata = metadata if metadata is not None else {}
        self.source = source
        self.document_type = document_type

        if not isinstance(self.text, str):
            raise ValueError("Document text must be a string")
        if not isinstance(self.metadata, dict):
            raise ValueError("Document metadata must be a dictionary")

    @property
    def content(self) -> str:
        """Backward-compatible alias for text used in some tests/call sites."""
        return self.text


class BaseLoader(ABC):
    """
    Abstract base class for document loaders.

    All document loaders must inherit from this class and implement
    the load method to provide consistent document loading interface.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the loader with configuration options.

        Args:
            **kwargs: Loader-specific configuration options
        """
        self.config = kwargs

    @abstractmethod
    async def load(self, source: str, **kwargs: Any) -> Document:
        """
        Load a document from the given source.

        Args:
            source: Source identifier (file path, URL, etc.)
            **kwargs: Additional loading options

        Returns:
            Document: Loaded document with content and metadata

        Raises:
            Exception: If document loading fails in the concrete implementation
        """
        pass

    @abstractmethod
    def validate_source(self, source: str) -> bool:
        """
        Validate if the source can be handled by this loader.

        Implementations should verify existence, accessibility and basic format
        expectations (e.g., file extension or MIME type).

        Args:
            source: Source identifier to validate

        Returns:
            bool: True if source can be handled, False otherwise
        """
        pass

    def _preprocess_text(self, text: str) -> str:
        """
        Optional preprocessing hook for text normalization.

        Default implementation returns the input unchanged. Subclasses can
        override to apply Unicode normalization, whitespace fixes, or language-
        specific cleaning.

        Args:
            text: Raw text extracted by the loader

        Returns:
            str: Normalized text
        """
        return text

    def _postprocess_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optional postprocessing hook for metadata normalization.

        Default implementation returns the input. Subclasses can override to
        enforce schema for keys like 'source_type', 'page', 'span', 'language'.

        Args:
            metadata: Raw metadata

        Returns:
            Dict[str, Any]: Normalized metadata
        """
        return metadata

    def get_supported_extensions(self) -> list[str]:
        """
        Get list of supported file extensions.

        Returns:
            list[str]: List of supported extensions (e.g., ['.pdf', '.txt'])
        """
        return []

    def get_loader_info(self) -> Dict[str, Any]:
        """
        Get information about this loader.

        Returns:
            Dict[str, Any]: Loader information including name, version, etc.
        """
        return {
            "name": self.__class__.__name__,
            "supported_extensions": self.get_supported_extensions(),
            "config": self.config,
            "schema_hint": {
                "metadata_keys": [
                    "source_type",
                    "page",
                    "span",
                    "language",
                    "mime_type",
                ]
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the loader.

        Returns:
            Dict[str, Any]: Health status information
        """
        import time

        try:
            # Basic health check - verify loader is properly initialized
            loader_info = self.get_loader_info()

            return {
                "status": "healthy",
                "loader_name": loader_info["name"],
                "supported_extensions": loader_info["supported_extensions"],
                "config_loaded": bool(self.config),
                "last_check": time.time(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "loader_name": self.__class__.__name__,
                "error": str(e),
                "last_check": time.time(),
            }


class DocumentLoader(BaseLoader):
    """
    Document loader interface for Multi-Format support.

    This class provides a simplified interface for document loading
    that's compatible with the new Multi-Format loaders.
    """

    async def load(self, source: str, **kwargs: Any) -> Document:
        """
        Load a document from the given file path.

        Args:
            source: Path/identifier to the document
            **kwargs: Additional loader-specific options

        Returns:
            Document: Loaded document with text and metadata
        """
        raise NotImplementedError("Subclasses must implement load method")

    def validate_source(self, source: str) -> bool:
        """
        Validate if the source can be handled by this loader.

        Args:
            source: Source identifier to validate

        Returns:
            bool: True if source can be handled, False otherwise
        """
        return True
