"""FastAPI dependency providers for RAGBot services."""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status

from ragbot.configs.settings import settings
from ragbot.services.integration_service import (
    IntegrationService,
    get_integration_service,
)
from ragbot.services.rag_service import RAGService


async def get_tenant_context(
    request: Request,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
) -> Optional[str]:
    """Retrieve optional tenant context from X-Tenant-ID header if multi-tenancy is enabled."""
    if not getattr(getattr(settings, "multi_tenant", object()), "enabled", False):
        return None
    return x_tenant_id


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
