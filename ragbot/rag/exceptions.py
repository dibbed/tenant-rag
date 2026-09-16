"""
Custom exceptions for the RAG system.

This module defines custom exception classes for better error handling
and debugging throughout the RAG pipeline.
"""

from typing import Any, Optional


class RAGError(Exception):
    """Base exception for RAG operations."""

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        """
        Initialize RAG error.

        Args:
            message: Error message
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class DocumentProcessingError(RAGError):
    """Exception raised during document processing."""

    def __init__(
        self,
        message: str,
        document_type: Optional[str] = None,
        source: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        """
        Initialize document processing error.

        Args:
            message: Error message
            document_type: Type of document being processed
            source: Source of the document (file path, URL, etc.)
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.document_type = document_type
        self.source = source


class EmbeddingError(RAGError):
    """Exception raised during embedding generation."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        """
        Initialize embedding error.

        Args:
            message: Error message
            provider: Embedding provider (openai, huggingface, etc.)
            model: Model name
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.provider = provider
        self.model = model


class VectorStoreError(RAGError):
    """Exception raised during vector store operations."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        store_type: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        """
        Initialize vector store error.

        Args:
            message: Error message
            operation: Operation being performed (upsert, query, etc.)
            store_type: Type of vector store (faiss, chromadb, qdrant, weaviate, etc.)
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.operation = operation
        self.store_type = store_type


class RetrievalError(RAGError):
    """Exception raised during document retrieval."""

    def __init__(
        self, message: str, query: Optional[str] = None, details: Optional[Any] = None
    ) -> None:
        """
        Initialize retrieval error.

        Args:
            message: Error message
            query: Query that caused the error
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.query = query


class LLMError(RAGError):
    """Exception raised during LLM operations."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        prompt_length: Optional[int] = None,
        details: Optional[Any] = None,
    ) -> None:
        """
        Initialize LLM error.

        Args:
            message: Error message
            provider: LLM provider (openai, anthropic, etc.)
            model: Model name
            prompt_length: Length of the prompt that caused the error
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.provider = provider
        self.model = model
        self.prompt_length = prompt_length


class ConfigurationError(RAGError):
    """Exception raised for configuration-related errors."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        """
        Initialize configuration error.

        Args:
            message: Error message
            config_key: Configuration key that caused the error
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.config_key = config_key


class RateLimitError(RAGError):
    """Exception raised when rate limits are exceeded."""

    def __init__(
        self,
        message: str,
        user_id: Optional[int] = None,
        retry_after: Optional[int] = None,
        details: Optional[Any] = None,
    ) -> None:
        """
        Initialize rate limit error.

        Args:
            message: Error message
            user_id: User ID that exceeded the rate limit
            retry_after: Seconds to wait before retrying
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.user_id = user_id
        self.retry_after = retry_after


class ValidationError(RAGError):
    """Exception raised for input validation errors."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Any] = None,
    ) -> None:
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field that failed validation
            value: Value that failed validation
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.field = field
        self.value = value


# Aliases for backward compatibility and consistency
RAGBotException = RAGError
AuthenticationError = ConfigurationError  # For auth-related config errors
