"""
Document Processing Service.

This module provides the DocumentService class for document management,
validation, preprocessing, and metadata tracking.
"""

import hashlib
import mimetypes
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import DocumentProcessingError
from ragbot.rag.loaders.advanced_loaders import AdvancedDocumentLoader


@dataclass
class ProcessingStats:
    """Document processing statistics."""

    original_size: int
    processed_size: int
    processing_time: float
    validation_time: float
    loader_type: str
    file_type: Optional[str] = None
    encoding: Optional[str] = None
    language_detected: Optional[str] = None


@dataclass
class ProcessedDocument:
    """Enhanced document with processing metadata."""

    content: str
    metadata: Dict[str, Any]
    source: str
    document_type: str
    processing_stats: ProcessingStats
    document_id: str
    created_at: datetime
    file_hash: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of document validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    file_info: Dict[str, Any]
    security_check: Dict[str, Any]


class DocumentService:
    """
    Service for document processing and management.

    This service handles document validation, preprocessing, file type detection,
    and processing statistics tracking.
    """

    def __init__(
        self, loaders=None, chunker=None, embedder=None, vector_store=None, cache=None
    ) -> None:
        """Initialize the document service."""
        # Store components for potential use
        self.loaders = loaders
        self.chunker = chunker
        self.embedder = embedder
        self.vector_store = vector_store
        self.cache = cache

        # Initialize Advanced Document Loader for Multi-Format support
        self.advanced_loader = AdvancedDocumentLoader()

        # Supported file extensions mapping (updated for Multi-Format)
        self.extension_mapping = {
            ".pdf": "pdf",
            ".txt": "text",
            ".docx": "docx",
            ".pptx": "pptx",
            ".xlsx": "xlsx",
            ".html": "html",
            ".htm": "html",
            ".md": "markdown",
            ".png": "image",
            ".jpg": "image",
            ".jpeg": "image",
            ".tiff": "image",
            ".bmp": "image",
            ".rst": "text",
            ".py": "text",
            ".js": "text",
            ".xml": "text",
            ".json": "text",
            ".csv": "text",
            ".tsv": "text",
        }

        # MIME type mapping (updated for Multi-Format)
        self.mime_mapping = {
            "application/pdf": "pdf",
            "text/plain": "text",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "text/markdown": "markdown",
            "text/html": "html",
            "text/xml": "text",
            "application/json": "text",
            "text/csv": "text",
            "image/png": "image",
            "image/jpeg": "image",
            "image/tiff": "image",
            "image/bmp": "image",
        }

        logger.info("Document service initialized successfully")

    async def validate_document(
        self, source: str, source_type: str
    ) -> ValidationResult:
        """
        Validate a document before processing.

        Args:
            source: Document source
            source_type: Document type

        Returns:
            ValidationResult: Validation result with errors and warnings
        """
        errors = []
        warnings = []
        file_info = {}
        security_check = {"passed": True, "issues": []}
        t0 = time.time()

        try:
            if source_type in {"pdf", "docx"} or (
                source_type == "text" and os.path.isfile(source)
            ):
                # File-based validation
                if not os.path.isfile(source):
                    errors.append(f"File not found: {source}")
                    return ValidationResult(
                        is_valid=False,
                        errors=errors,
                        warnings=warnings,
                        file_info=file_info,
                        security_check=security_check,
                    )

                # Check file size
                file_size = os.path.getsize(source)
                max_size_bytes = settings.security.max_file_size_mb * 1024 * 1024

                if file_size > max_size_bytes:
                    errors.append(
                        f"File too large: {file_size} bytes "
                        f"(max: {max_size_bytes} bytes)"
                    )

                # Check file extension and sanitize path
                file_ext = Path(source).suffix.lower()
                abs_path = str(Path(source).expanduser().resolve())

                if source_type == "pdf" and file_ext != ".pdf":
                    errors.append(f"Invalid PDF file extension: {file_ext}")
                if source_type == "docx" and file_ext != ".docx":
                    errors.append(f"Invalid DOCX file extension: {file_ext}")

                # Get MIME type
                mime_type, _ = mimetypes.guess_type(source)

                # Check allowed file types
                try:
                    allowed = {
                        str(t).lower() for t in settings.security.allowed_file_types
                    }
                except Exception:
                    allowed = set()

                if source_type not in allowed:
                    warnings.append(
                        f"Source type not explicitly allowed: {source_type}"
                    )

                # MIME vs extension mismatch warning
                if mime_type and file_ext:
                    expected = self.mime_mapping.get(mime_type)
                    from_ext = self.extension_mapping.get(file_ext, None)
                    if expected and from_ext and expected != from_ext:
                        warnings.append(
                            f"MIME/extension mismatch: mime={mime_type}, ext={file_ext}"
                        )
                        try:
                            logger.warning(
                                "MIME/extension mismatch",
                                mime=mime_type,
                                ext=file_ext,
                                path=abs_path,
                            )
                        except Exception:
                            pass

                file_info = {
                    "size": file_size,
                    "type": mime_type,
                    "extension": file_ext,
                    "path": abs_path,
                }

                # Security checks
                if file_size == 0:
                    security_check["issues"].append("Empty file")

                # Check for suspicious file names
                suspicious_patterns = ["../", "..\\", "<script", "javascript:"]
                filename = os.path.basename(source)
                for pattern in suspicious_patterns:
                    if pattern in filename.lower():
                        security_check["issues"].append(
                            f"Suspicious filename pattern: {pattern}"
                        )
                        security_check["passed"] = False

            elif source_type == "url":
                # URL validation
                parsed_url = urlparse(source)

                if not parsed_url.scheme in ["http", "https"]:
                    errors.append(f"Invalid URL scheme: {parsed_url.scheme}")

                if not parsed_url.netloc:
                    errors.append("Invalid URL: missing domain")

                # Security checks for URLs
                suspicious_domains = ["localhost", "127.0.0.1", "0.0.0.0"]
                if parsed_url.netloc.lower() in suspicious_domains:
                    warnings.append(f"Potentially unsafe domain: {parsed_url.netloc}")

                file_info = {
                    "url": source,
                    "domain": parsed_url.netloc,
                    "scheme": parsed_url.scheme,
                }

            elif source_type == "text":
                # Direct text validation
                if not source or not source.strip():
                    errors.append("Empty text content")

                text_size = len(source.encode("utf-8"))
                max_size_bytes = settings.security.max_file_size_mb * 1024 * 1024

                if text_size > max_size_bytes:
                    errors.append(
                        f"Text too large: {text_size} bytes "
                        f"(max: {max_size_bytes} bytes)"
                    )

                file_info = {
                    "size": text_size,
                    "type": "text/plain",
                    "encoding": "utf-8",
                }

            else:
                errors.append(f"Unsupported source type: {source_type}")

            # Final security check
            if security_check["issues"]:
                security_check["passed"] = False

            is_valid = len(errors) == 0 and security_check["passed"]
            validation_time = time.time() - t0
            file_info["validation_duration_sec"] = validation_time

            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                file_info=file_info,
                security_check=security_check,
            )

        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                file_info=file_info,
                security_check={"passed": False, "issues": [str(e)]},
            )

    def detect_source_type(self, source: str) -> str:
        """
        Detect the type of document source.

        Args:
            source: Document source

        Returns:
            str: Detected source type (pdf, url, text)
        """
        # Check if it's a URL
        if source.startswith(("http://", "https://")):
            return "url"

        # Check if it's a file path
        if os.path.isfile(source):
            file_ext = Path(source).suffix.lower()
            return self.extension_mapping.get(file_ext, "text")

        # Check MIME type if available
        mime_type, _ = mimetypes.guess_type(source)
        if mime_type in self.mime_mapping:
            return self.mime_mapping[mime_type]

        # Default to text for direct content
        return "text"

    async def load_document_with_multi_format(
        self, file_path: str
    ) -> ProcessedDocument:
        """
        Load document using Advanced Multi-Format support.

        Args:
            file_path: Path to the document file

        Returns:
            ProcessedDocument: Processed document with metadata

        Raises:
            DocumentProcessingError: If document loading fails
        """
        try:
            # Validate file first
            t_valid = time.time()
            validation = await self.advanced_loader.validate_file(file_path)
            validation_time = time.time() - t_valid

            if not validation["is_valid"]:
                raise DocumentProcessingError(
                    f"File validation failed: {validation['error']}"
                )

            # Load document using AdvancedDocumentLoader
            t_load = time.time()
            document = await self.advanced_loader.load_document(file_path)
            load_time = time.time() - t_load

            # Create processing stats
            processing_stats = ProcessingStats(
                original_size=validation["size"],
                processed_size=len(document.text),
                processing_time=load_time,
                validation_time=validation_time,
                loader_type="AdvancedDocumentLoader",
                file_type=validation["format"],
                encoding="utf-8",
                language_detected=None,
            )

            # Create processed document
            processed_doc = ProcessedDocument(
                content=document.text,
                metadata=document.metadata,
                source=file_path,
                document_type=document.metadata.get("type", "unknown"),
                processing_stats=processing_stats,
                document_id=hashlib.md5(file_path.encode()).hexdigest(),
                created_at=datetime.now(),
                file_hash=hashlib.md5(document.text.encode()).hexdigest(),
            )

            logger.info(
                f"Document loaded successfully: {file_path} ({validation['format']})"
            )
            return processed_doc

        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {str(e)}")
            raise DocumentProcessingError(f"Document loading failed: {str(e)}") from e

    async def get_supported_formats(self) -> Dict[str, str]:
        """
        Get list of supported file formats.

        Returns:
            Dict[str, str]: Dictionary of supported formats and descriptions
        """
        return await self.advanced_loader.get_supported_formats()

    def generate_document_id(self, source: str, source_type: str) -> str:
        """
        Generate a unique document ID.

        Args:
            source: Document source
            source_type: Document type

        Returns:
            str: Unique document ID
        """
        timestamp = int(time.time() * 1000)  # milliseconds
        source_hash = hashlib.md5(source.encode()).hexdigest()[:8]
        return f"{source_type}_{source_hash}_{timestamp}"

    def calculate_content_hash(self, content: str) -> str:
        """
        Calculate hash of document content.

        Args:
            content: Document content

        Returns:
            str: Content hash
        """
        return hashlib.sha256(content.encode()).hexdigest()

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the document service.

        Returns:
            Dict[str, Any]: Health status information
        """
        try:
            # Test basic functionality
            test_source = "test.txt"
            test_content = "This is a test document for health check."

            # Test source type detection
            detected_type = self.detect_source_type(test_source)

            # Test document ID generation
            doc_id = self.generate_document_id(test_source, "text")

            # Test content hash calculation
            content_hash = self.calculate_content_hash(test_content)

            # Test advanced loader availability
            supported_formats = await self.get_supported_formats()

            return {
                "status": "healthy",
                "service_name": "DocumentService",
                "components_available": {
                    "loaders": self.loaders is not None,
                    "chunker": self.chunker is not None,
                    "embedder": self.embedder is not None,
                    "vector_store": self.vector_store is not None,
                    "cache": self.cache is not None,
                    "advanced_loader": self.advanced_loader is not None,
                },
                "supported_formats_count": len(supported_formats),
                "extension_mapping_count": len(self.extension_mapping),
                "mime_mapping_count": len(self.mime_mapping),
                "test_functions_working": {
                    "source_type_detection": detected_type == "text",
                    "document_id_generation": bool(doc_id),
                    "content_hash_calculation": bool(content_hash),
                },
                "last_check": time.time(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "service_name": "DocumentService",
                "error": str(e),
                "last_check": time.time(),
            }
