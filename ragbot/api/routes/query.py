"""RAG Query routes."""

from __future__ import annotations

import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from ragbot.api.dependencies import (
    get_integration_service_dep,
    get_rag_service_dep,
    get_tenant_context,
)
from ragbot.api.schemas.query import QueryRequest, QueryResponse
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import EmbeddingError, LLMError, VectorStoreError
from ragbot.services.integration_service import IntegrationService
from ragbot.services.rag_service import QueryResult, RAGService

router = APIRouter(prefix="/api/v1", tags=["Query"])


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    payload: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service_dep),
    integration_service: IntegrationService = Depends(get_integration_service_dep),
    tenant_id: Optional[str] = Depends(get_tenant_context),
) -> QueryResponse:
    """
    Execute a RAG query against the ingested knowledge base.

    Preserves structured answers, citations, confidence scores, and processing metadata.
    """
    start_time = time.time()
    lang = payload.language or settings.default_lang

    try:
        result: QueryResult = await rag_service.query_documents(
            question=payload.question,
            lang=lang,
            top_k=payload.top_k,
            similarity_threshold=payload.similarity_threshold,
            tenant_id=tenant_id,
        )

        processing_time = time.time() - start_time

        # Track user action best-effort without blocking
        try:
            await integration_service.track_user_action(
                user_id="api_user",
                action="query",
                details={
                    "query": payload.question[:100],
                    "processing_time": processing_time,
                    "confidence_score": getattr(result, "confidence_score", None),
                    "sources_count": len(result.sources) if result.sources else 0,
                },
            )
        except Exception:
            pass

        return QueryResponse(
            answer=result.answer,
            sources=result.sources or [],
            confidence_score=result.confidence_score or 0.0,
            processing_time=getattr(result, "processing_time", processing_time) or processing_time,
            language=getattr(result, "language", lang) or lang,
            retrieved_chunks=getattr(result, "retrieved_chunks", None),
            metadata=getattr(result, "metadata", None),
        )

    except (EmbeddingError, LLMError) as exc:
        logger.error(f"External model provider failure during query: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model provider service unavailable",
        ) from exc
    except VectorStoreError as exc:
        logger.error(f"Vector store search failure during query: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vector store query failure",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error during query execution: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process query due to an internal error",
        ) from exc
