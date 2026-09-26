"""Aggregate API router."""

from fastapi import APIRouter, Depends

from ragbot.api.dependencies import enforce_rate_limit
from ragbot.api.routes.documents import router as documents_router
from ragbot.api.routes.health import router as health_router
from ragbot.api.routes.query import router as query_router

router = APIRouter()
router.include_router(health_router)
# Security (C9): every API router except health counts requests after
# authentication, against the Principal. Health checks are never rate limited.
router.include_router(query_router, dependencies=[Depends(enforce_rate_limit)])
router.include_router(documents_router, dependencies=[Depends(enforce_rate_limit)])

__all__ = ["router"]
