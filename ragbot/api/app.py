"""FastAPI Application factory and lifecycle management."""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ragbot.api.access_mode import log_access_mode_warnings
from ragbot.api.edge.config import (
    build_rate_limiter,
    load_edge_config,
    log_edge_protection_mode,
)
from ragbot.api.edge.rate_limiter import RateLimitExceeded, rate_limit_exceeded_handler
from ragbot.api.middleware.body_size_limit import BodySizeLimitMiddleware
from ragbot.api.middleware.rate_limit import RateLimitMiddleware
from ragbot.api.middleware.trusted_proxy import TrustedProxyMiddleware
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
        if getattr(app.state, "integration_service", None) is not None:
            integration_service = app.state.integration_service
            if not getattr(integration_service, "_initialized", False):
                await integration_service.initialize()
            app.state.rag_service = integration_service.get_rag_service()
        else:
            integration_service = await get_integration_service()
            app.state.integration_service = integration_service
            app.state.rag_service = integration_service.get_rag_service()

        # Initialize plugin system if enabled
        if app.state.rag_service:
            from ragbot.configs.settings import settings

            plugins_cfg = getattr(settings, "plugins", object())
            if getattr(plugins_cfg, "enabled", False) or getattr(
                settings, "auto_load_plugins", False
            ):
                if hasattr(app.state.rag_service, "initialize_plugin_system"):
                    await app.state.rag_service.initialize_plugin_system()

        logger.info("RAGBot application services initialized successfully")
    except Exception as exc:
        logger.error(f"Failed to initialize shared services during startup: {exc}")
        app.state.integration_service = None
        app.state.rag_service = None

    # Security (C9): delete expired rate limit records even when no request
    # arrives, and release the shared rate limit store on shutdown.
    rate_limiter = getattr(app.state, "rate_limiter", None)
    if rate_limiter is not None:
        rate_limiter.start_background_sweep()

    yield

    logger.info("Shutting down RAGBot API application services...")
    if rate_limiter is not None:
        await rate_limiter.aclose()
    try:
        # Gracefully stop active plugins
        if app.state.rag_service and getattr(
            app.state.rag_service, "plugin_manager", None
        ):
            try:
                active_pids = list(
                    app.state.rag_service.plugin_manager.active_plugins.keys()
                )
                for pid in active_pids:
                    await app.state.rag_service.plugin_manager.stop_plugin(pid)
            except Exception as plug_err:
                logger.warning(f"Error stopping plugins during shutdown: {plug_err}")

        svc = getattr(app.state, "integration_service", None)
        if svc is not None and hasattr(svc, "shutdown"):
            shutdown_res = svc.shutdown()
            if inspect.isawaitable(shutdown_res):
                await shutdown_res
        await shutdown_integration_service()
        logger.info("RAGBot API application shutdown complete")
    except Exception as exc:
        logger.error(f"Error during application shutdown: {exc}")


def create_app(lifespan_context: Any = lifespan) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="TenantRAG API",
        description="Multi-Tenant RAG Microservice for SaaS Backends",
        version="1.0.0",
        lifespan=lifespan_context,
    )

    # Security (C9, C10, C11): edge protection settings. An invalid trusted
    # proxy entry, an invalid origin, or SECURITY_CORS_ALLOWED_ORIGINS='*'
    # outside ENVIRONMENT=development stops startup here.
    edge_config = load_edge_config()
    rate_limiter = build_rate_limiter(edge_config)
    app.state.edge_config = edge_config
    app.state.rate_limiter = rate_limiter

    # Middleware, outermost first:
    #   TrustedProxyMiddleware   sets the Client Address (SECURITY_TRUSTED_PROXIES)
    #   CORSMiddleware           answers preflights; CORS headers on every response
    #   RateLimitMiddleware      counts requests without credentials before the body
    #   BodySizeLimitMiddleware  rejects oversized bodies before and while reading
    # Starlette runs the middleware added last first, so they are added in
    # reverse order.
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)
    app.add_middleware(CORSMiddleware, **edge_config.cors.middleware_options())
    app.add_middleware(TrustedProxyMiddleware, trusted_proxies=edge_config.trusted_proxies)

    # Requests refused after authentication get the same 429 body as the others
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

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

    # Security (C5): report the effective authentication mode at startup.
    log_access_mode_warnings()

    # Security (C9, C10, C11): report the effective edge protection settings.
    log_edge_protection_mode(edge_config)

    # Include API routes
    app.include_router(api_router)

    return app


app = create_app()
