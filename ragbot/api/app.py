"""FastAPI Application factory and lifecycle management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ragbot.api.routes import router as api_router
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import (
    get_integration_service,
    shutdown_integration_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan context manager.

    Initializes heavy services (retriever, embedder, vector store, QA chain)
    once on startup and ensures clean shutdown and resource release on exit.
    """
    logger.info("Initializing RAGBot API application lifecycle...")
    try:
        integration_service = await get_integration_service()
        app.state.integration_service = integration_service
        app.state.rag_service = integration_service.get_rag_service()
        logger.info("RAGBot application services initialized successfully")
    except Exception as exc:
        logger.error(f"Failed to initialize shared services during startup: {exc}")
        app.state.integration_service = None
        app.state.rag_service = None

    yield

    logger.info("Shutting down RAGBot API application services...")
    try:
        await shutdown_integration_service()
        logger.info("RAGBot API application shutdown complete")
    except Exception as exc:
        logger.error(f"Error during application shutdown: {exc}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="RAGBot API",
        description="API-First Backend for Retrieval-Augmented Generation (RAG)",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration for web frontend clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global unhandled exception handler to prevent leaking internal tracebacks
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred"},
        )

    # Include API routes
    app.include_router(api_router)

    return app


app = create_app()
