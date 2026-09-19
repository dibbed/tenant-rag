"""RAG Query request and response schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """RAG query request payload."""

    question: str = Field(..., min_length=1, description="Question text to query RAG with")
    language: Optional[str] = Field(
        default=None, description="Language code (e.g. 'fa', 'en'). Defaults to system default"
    )
    top_k: Optional[int] = Field(
        default=None, ge=1, le=20, description="Optional chunk retrieval count override"
    )
    similarity_threshold: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Optional similarity threshold override"
    )


class QueryResponse(BaseModel):
    """Structured RAG query response preserving core metadata and citations."""

    answer: str = Field(description="Generated answer from RAG pipeline")
    sources: List[str] = Field(default_factory=list, description="Source citations")
    confidence_score: float = Field(default=0.0, description="Confidence score (0.0 - 1.0)")
    processing_time: float = Field(default=0.0, description="Execution time in seconds")
    language: str = Field(default="en", description="Detected or requested language")
    retrieved_chunks: Optional[List[str]] = Field(
        default=None, description="Raw retrieved text chunks if available"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Supplementary pipeline execution metadata"
    )
