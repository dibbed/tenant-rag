"""Document ingestion and store maintenance routes."""

from __future__ import annotations

import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ragbot.api.dependencies import get_integration_service_dep, get_rag_service_dep
from ragbot.api.schemas.documents import (
    IngestResponse,
    ResetResponse,
    TextIngestRequest,
    URLIngestRequest,
)
from ragbot.caching.cache_manager import cache_manager
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import DocumentProcessingError, VectorStoreError
from ragbot.services.integration_service import IntegrationService
from ragbot.services.rag_service import IngestResult, RAGService

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    rag_service: RAGService = Depends(get_rag_service_dep),
    integration_service: IntegrationService = Depends(get_integration_service_dep),
) -> IngestResponse:
    """
    Upload and ingest a document file (PDF, DOCX, TXT, HTML, MD, etc.).

    Validates file size and format, saves to a temporary location for ingestion,
    and guarantees reliable temporary file cleanup on both success and failure.
    """
    filename = Path(file.filename or "upload.bin").name
    suffix = Path(filename).suffix.lower()
    ext = suffix.lstrip(".")

    # Validate allowed extensions
    allowed_types = getattr(
        settings.security,
        "allowed_file_types",
        ["pdf", "docx", "txt", "html", "md", "pptx", "xlsx", "png", "jpg", "jpeg", "tiff", "bmp"],
    ) or []

    if ext and allowed_types and ext not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(allowed_types)}",
        )

    # Read content with size and empty checks
    max_mb = getattr(settings.security, "max_file_size_mb", 50)
    max_bytes = max_mb * 1024 * 1024

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_mb}MB",
        )

    # Write to temporary file with appropriate suffix
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix or ".pdf", delete=False) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)

        result: IngestResult = await rag_service.ingest_document(
            source=str(temp_path),
            source_type=None,  # Auto-detect from file suffix
            metadata={
                "source": filename,
                "file_name": filename,
                "original_filename": filename,
                "file_size": len(content),
            },
        )

        if not result.success:
            logger.warning(f"Document ingestion failed for {filename}: {result.error_message}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document processing failed: content unprocessable or invalid",
            )

        # Record metrics best-effort
        try:
            await integration_service.track_user_action(
                user_id="api_user",
                action="upload_document",
                details={
                    "filename": filename,
                    "chunks_created": result.chunks_created,
                    "processing_time": result.processing_time,
                },
            )
            await integration_service.record_document_type(ext or "unknown")
        except Exception:
            pass

        # Sanitize metadata to never leak server filesystem temp paths
        resp_metadata = dict(result.metadata or {})
        resp_metadata["source"] = filename
        resp_metadata.pop("temp_path", None)

        return IngestResponse(
            success=result.success,
            document_id=result.document_id,
            chunks_created=result.chunks_created,
            processing_time=result.processing_time,
            error_message=result.error_message,
            metadata=resp_metadata,
        )

    except (DocumentProcessingError, ValueError) as exc:
        logger.error(f"Document processing error for {filename}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document processing failed: content unprocessable or invalid",
        ) from exc
    except VectorStoreError as exc:
        logger.error(f"Vector store error during ingestion of {filename}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vector storage error",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error during ingestion of {filename}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while ingesting document",
        ) from exc
    finally:
        # Guarantee temporary file is cleaned up reliably
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as cleanup_err:
                logger.warning(f"Failed to delete temp file {temp_path}: {cleanup_err}")


@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    payload: TextIngestRequest,
    rag_service: RAGService = Depends(get_rag_service_dep),
    integration_service: IntegrationService = Depends(get_integration_service_dep),
) -> IngestResponse:
    """Ingest raw text content into the RAG knowledge base."""
    text = payload.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text content cannot be empty",
        )

    # Validate maximum text payload size to prevent memory exhaustion DoS
    max_mb = getattr(settings.security, "max_file_size_mb", 50)
    max_chars = max_mb * 1024 * 1024
    if len(text) > max_chars:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Text content exceeds maximum allowed size of {max_mb}MB",
        )

    title = payload.title or "direct_text"
    meta = dict(payload.metadata or {})
    meta["title"] = title
    meta["source"] = title
    meta["file_name"] = f"{title}.txt" if not title.endswith(".txt") else title

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(text)
            temp_path = Path(tmp.name)

        result: IngestResult = await rag_service.ingest_document(
            source=str(temp_path),
            source_type="text",
            metadata=meta,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Text processing failed: invalid or unprocessable content",
            )

        try:
            await integration_service.track_user_action(
                user_id="api_user",
                action="ingest_text",
                details={
                    "text_length": len(text),
                    "chunks_created": result.chunks_created,
                },
            )
            await integration_service.record_document_type("text")
        except Exception:
            pass

        resp_metadata = dict(result.metadata or {})
        resp_metadata["source"] = title
        resp_metadata.pop("temp_path", None)

        return IngestResponse(
            success=result.success,
            document_id=result.document_id,
            chunks_created=result.chunks_created,
            processing_time=result.processing_time,
            error_message=result.error_message,
            metadata=resp_metadata,
        )

    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Text processing failed: invalid or unprocessable content",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error ingesting text: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while ingesting text",
        ) from exc
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as cleanup_err:
                logger.warning(f"Failed to delete temp text file {temp_path}: {cleanup_err}")


@router.post("/url", response_model=IngestResponse)
async def ingest_url(
    payload: URLIngestRequest,
    rag_service: RAGService = Depends(get_rag_service_dep),
    integration_service: IntegrationService = Depends(get_integration_service_dep),
) -> IngestResponse:
    """Fetch and ingest content from a specified URL."""
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http:// or https://",
        )

    try:
        result: IngestResult = await rag_service.ingest_document(
            source=url,
            source_type="url",
            metadata=payload.metadata,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result.error_message or "URL ingestion failed",
            )

        try:
            await integration_service.track_user_action(
                user_id="api_user",
                action="ingest_url",
                details={"url": url, "chunks_created": result.chunks_created},
            )
            await integration_service.record_document_type("url")
        except Exception:
            pass

        return IngestResponse(
            success=result.success,
            document_id=result.document_id,
            chunks_created=result.chunks_created,
            processing_time=result.processing_time,
            error_message=result.error_message,
            metadata=result.metadata,
        )

    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="URL document processing failed",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error ingesting URL {url}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while ingesting URL",
        ) from exc


@router.post("/reset", response_model=ResetResponse)
async def reset_store(
    rag_service: RAGService = Depends(get_rag_service_dep),
    integration_service: IntegrationService = Depends(get_integration_service_dep),
) -> ResetResponse:
    """
    Clear all documents from the vector store and invalidate all cache layers.

    Resets the repository knowledge base to a zero state.
    """
    try:
        if hasattr(rag_service, "reset_vector_store"):
            maybe = rag_service.reset_vector_store()
            success = await maybe if hasattr(maybe, "__await__") else maybe
        else:
            success = await rag_service.reset_store()

        cache_cleared = True
        try:
            # Clear active IntegrationService cache component if present
            int_cache = getattr(integration_service, "components", {}).get("cache")
            if int_cache is not None:
                if hasattr(int_cache, "clear"):
                    await int_cache.clear()
                if hasattr(int_cache, "clear_semantic_cache"):
                    await int_cache.clear_semantic_cache()

            # Clear global cache_manager singleton
            await cache_manager.initialize()
            l12_ok = await cache_manager.clear()
            sem_ok = await cache_manager.clear_semantic_cache()
            cache_cleared = bool(l12_ok and (sem_ok or True))
        except Exception as cache_err:
            logger.warning(f"Cache clear during reset partially failed: {cache_err}")
            cache_cleared = False

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset vector store",
            )

        return ResetResponse(
            success=True,
            message="Vector store and cache successfully reset",
            cache_cleared=cache_cleared,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error resetting store: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reset operation failed due to an internal error",
        ) from exc
