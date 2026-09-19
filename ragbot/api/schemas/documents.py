"""Document ingestion and store maintenance schemas."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class TextIngestRequest(BaseModel):
    """Request schema for direct text ingestion."""

    text: str = Field(..., min_length=1, description="Raw text content to ingest")
    title: Optional[str] = Field(default=None, description="Optional document title or identifier")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional metadata to attach to the ingested chunks"
    )


class URLIngestRequest(BaseModel):
    """Request schema for URL ingestion."""

    url: str = Field(..., min_length=1, description="HTTP/HTTPS URL of document or webpage")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional metadata to attach to the ingested chunks"
    )


class IngestResponse(BaseModel):
    """Structured response from document ingestion operation."""

    success: bool = Field(description="Whether ingestion succeeded")
    document_id: str = Field(description="Assigned unique identifier for the ingested document")
    chunks_created: int = Field(default=0, description="Number of text chunks created and stored")
    processing_time: float = Field(default=0.0, description="Processing duration in seconds")
    error_message: Optional[str] = Field(default=None, description="Error detail if ingestion failed")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional ingestion metadata")


class ResetResponse(BaseModel):
    """Response model for vector store and cache reset operation."""

    success: bool = Field(description="Whether the reset operation succeeded")
    message: str = Field(description="Descriptive status message")
    cache_cleared: bool = Field(default=True, description="Whether cache layers were flushed")
