"""Health and status check routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from ragbot.api.dependencies import get_integration_service_dep
from ragbot.api.schemas.health import HealthResponse
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import IntegrationService

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
@router.get("/api/v1/health", response_model=HealthResponse)
async def get_health(
    response: Response,
    integration_service: IntegrationService = Depends(get_integration_service_dep),
) -> HealthResponse:
    """
    Get system health and component status.

    Returns HTTP 200 when healthy or degraded, and HTTP 503 when unhealthy.
    Does not leak secrets or internal environment variables.
    """
    try:
        health_data = await integration_service.health_check()
    except Exception as exc:
        logger.error(f"Health check execution failed: {exc}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        import time

        return HealthResponse(
            status="unhealthy",
            timestamp=time.time(),
            components={},
            issues=[f"Health check exception: {str(exc)}"],
        )

    system_status = health_data.get("status", "unknown")
    if system_status == "unhealthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=system_status,
        timestamp=health_data.get("timestamp", 0.0),
        components=health_data.get("components", {}),
        issues=health_data.get("issues", []),
    )
