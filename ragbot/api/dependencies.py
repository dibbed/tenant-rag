"""FastAPI dependency providers for RAGBot services."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from ragbot.services.integration_service import (
    IntegrationService,
    get_integration_service,
)
from ragbot.services.rag_service import RAGService


async def get_integration_service_dep(request: Request) -> IntegrationService:
    """Retrieve shared IntegrationService instance from app state or singleton."""
    if (
        hasattr(request.app.state, "integration_service")
        and request.app.state.integration_service is not None
    ):
        return request.app.state.integration_service
    return await get_integration_service()


async def get_rag_service_dep(
    integration_service: IntegrationService = Depends(get_integration_service_dep),
) -> RAGService:
    """Retrieve shared RAGService instance from integration service."""
    rag_service = integration_service.get_rag_service()
    if rag_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAGService is not available or failed to initialize",
        )
    return rag_service
