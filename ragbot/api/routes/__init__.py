"""Aggregate API router."""

from fastapi import APIRouter

from ragbot.api.routes.documents import router as documents_router
from ragbot.api.routes.health import router as health_router
from ragbot.api.routes.query import router as query_router

router = APIRouter()
router.include_router(health_router)
router.include_router(query_router)
router.include_router(documents_router)

__all__ = ["router"]
