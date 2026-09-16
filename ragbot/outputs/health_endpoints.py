"""
Health check endpoints for external monitoring.

This module provides HTTP endpoints for health monitoring that can be used
by external monitoring systems, load balancers, and orchestration platforms.
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from ragbot.outputs.health import HealthStatus, health_checker
from ragbot.outputs.logger import logger
from ragbot.services.graceful_degradation import graceful_degradation


class HealthEndpoints:
    """
    Health check endpoints for external monitoring.

    Provides REST API endpoints for health monitoring that can be consumed
    by external systems for monitoring, alerting, and load balancing decisions.
    """

    def __init__(self, app: Optional[Any] = None) -> None:
        """
        Initialize health endpoints.

        Args:
            app: Optional FastAPI app instance to register routes with
        """
        self.app = app
        self._setup_endpoints()

        logger.info("Health endpoints initialized", fastapi_available=FASTAPI_AVAILABLE)

    def _setup_endpoints(self) -> None:
        """Setup health check endpoints."""
        if not FASTAPI_AVAILABLE or not self.app:
            logger.warning(
                "FastAPI not available or no app provided - health endpoints disabled"
            )
            return

        # Register health check routes
        self.app.get("/health")(self.health_check)
        self.app.get("/health/live")(self.liveness_probe)
        self.app.get("/health/ready")(self.readiness_probe)
        self.app.get("/health/detailed")(self.detailed_health_check)
        self.app.get("/health/components")(self.component_health_check)
        self.app.get("/health/metrics")(self.health_metrics)

        logger.info("Health endpoints registered")

    async def health_check(self) -> JSONResponse:
        """
        Basic health check endpoint.

        Returns:
            JSONResponse: Basic health status
        """
        try:
            system_health = await health_checker.check_all_components()

            status_code = 200
            if system_health.overall_status == HealthStatus.UNHEALTHY:
                status_code = 503
            elif system_health.overall_status == HealthStatus.DEGRADED:
                status_code = 200  # Still serving traffic but with warnings

            response_data = {
                "status": system_health.overall_status.value,
                "timestamp": system_health.timestamp.isoformat(),
                "uptime": system_health.uptime,
            }

            return JSONResponse(content=response_data, status_code=status_code)

        except Exception as e:
            logger.error(f"Health check endpoint failed: {e}")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=500,
            )

    async def liveness_probe(self) -> JSONResponse:
        """
        Kubernetes-style liveness probe.

        This endpoint indicates whether the application is running and should
        be restarted if it fails. It performs minimal checks.

        Returns:
            JSONResponse: Liveness status
        """
        try:
            # Basic liveness check - just verify the application is responsive
            response_data = {
                "status": "alive",
                "timestamp": datetime.now().isoformat(),
                "uptime": health_checker.start_time,
            }

            return JSONResponse(content=response_data, status_code=200)

        except Exception as e:
            logger.error(f"Liveness probe failed: {e}")
            return JSONResponse(
                content={
                    "status": "dead",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=500,
            )

    async def readiness_probe(self) -> JSONResponse:
        """
        Kubernetes-style readiness probe.

        This endpoint indicates whether the application is ready to serve traffic.
        It performs more comprehensive checks than the liveness probe.

        Returns:
            JSONResponse: Readiness status
        """
        try:
            # Check critical components for readiness
            critical_checks = [
                health_checker.check_telegram_api(),
                health_checker.check_llm_service(),
                health_checker.check_vector_store(),
            ]

            results = await asyncio.gather(*critical_checks, return_exceptions=True)

            # Check if any critical component failed
            ready = True
            failed_components = []

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    ready = False
                    failed_components.append(f"check_{i}_exception")
                elif result.status == HealthStatus.UNHEALTHY:
                    ready = False
                    failed_components.append(result.name)

            status_code = 200 if ready else 503

            response_data = {
                "status": "ready" if ready else "not_ready",
                "timestamp": datetime.now().isoformat(),
                "failed_components": failed_components,
            }

            return JSONResponse(content=response_data, status_code=status_code)

        except Exception as e:
            logger.error(f"Readiness probe failed: {e}")
            return JSONResponse(
                content={
                    "status": "not_ready",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=503,
            )

    async def detailed_health_check(self) -> JSONResponse:
        """
        Detailed health check with full component information.

        Returns:
            JSONResponse: Detailed health status
        """
        try:
            system_health = await health_checker.check_all_components()

            status_code = 200
            if system_health.overall_status == HealthStatus.UNHEALTHY:
                status_code = 503
            elif system_health.overall_status == HealthStatus.DEGRADED:
                status_code = 200

            return JSONResponse(
                content=system_health.to_dict(), status_code=status_code
            )

        except Exception as e:
            logger.error(f"Detailed health check failed: {e}")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=500,
            )

    async def component_health_check(
        self, component: Optional[str] = None
    ) -> JSONResponse:
        """
        Check health of specific component(s).

        Args:
            component: Optional component name to check

        Returns:
            JSONResponse: Component health status
        """
        try:
            if component:
                # Check specific component
                if component not in health_checker.component_health:
                    return JSONResponse(
                        content={
                            "error": f"Component '{component}' not found",
                            "available_components": list(
                                health_checker.component_health.keys()
                            ),
                        },
                        status_code=404,
                    )

                component_health = health_checker.component_health[component]
                status_code = (
                    200 if component_health.status == HealthStatus.HEALTHY else 503
                )

                return JSONResponse(
                    content=component_health.to_dict(), status_code=status_code
                )
            else:
                # Return all components
                components = {
                    name: comp.to_dict()
                    for name, comp in health_checker.component_health.items()
                }

                return JSONResponse(content={"components": components}, status_code=200)

        except Exception as e:
            logger.error(f"Component health check failed: {e}")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=500,
            )

    async def health_metrics(self) -> JSONResponse:
        """
        Health metrics endpoint for monitoring systems.

        Returns:
            JSONResponse: Health metrics in a format suitable for monitoring
        """
        try:
            health_summary = health_checker.get_health_summary()

            # Convert to metrics format
            metrics = {
                "ragbot_health_status": {
                    "value": 1 if health_summary["status"] == "healthy" else 0,
                    "labels": {"status": health_summary["status"]},
                },
                "ragbot_uptime_seconds": {"value": health_summary["uptime"]},
                "ragbot_components_total": {
                    "value": health_summary["summary"]["total_components"]
                },
                "ragbot_components_healthy": {
                    "value": health_summary["summary"]["healthy"]
                },
                "ragbot_components_degraded": {
                    "value": health_summary["summary"]["degraded"]
                },
                "ragbot_components_unhealthy": {
                    "value": health_summary["summary"]["unhealthy"]
                },
                "ragbot_components_unknown": {
                    "value": health_summary["summary"]["unknown"]
                },
            }

            # Add graceful degradation metrics
            try:
                gd_metrics = graceful_degradation.get_performance_metrics()
                gd_status = graceful_degradation.get_system_status()

                metrics.update(
                    {
                        "ragbot_graceful_degradation_status": {
                            "value": 1
                            if gd_status["overall_status"] == "healthy"
                            else 0,
                            "labels": {"status": gd_status["overall_status"]},
                        },
                        "ragbot_graceful_degradation_services_total": {
                            "value": gd_status["total_services"]
                        },
                        "ragbot_graceful_degradation_services_healthy": {
                            "value": gd_status["healthy_services"]
                        },
                        "ragbot_graceful_degradation_services_degraded": {
                            "value": gd_status["degraded_services"]
                        },
                        "ragbot_graceful_degradation_services_critical": {
                            "value": gd_status["critical_services"]
                        },
                    }
                )

                # Add fallback counts per service
                for service_name, fallback_count in gd_metrics[
                    "fallback_counts"
                ].items():
                    metrics[f"ragbot_fallback_count_{service_name}"] = {
                        "value": fallback_count,
                        "labels": {"service": service_name},
                    }

            except Exception as e:
                logger.warning(f"Failed to add graceful degradation metrics: {e}")

            # Add per-component metrics
            for comp_name, comp_data in health_summary["components"].items():
                metrics["ragbot_component_status"] = {
                    "value": 1 if comp_data["status"] == "healthy" else 0,
                    "labels": {"component": comp_name, "status": comp_data["status"]},
                }

                if comp_data["response_time"] is not None:
                    metrics["ragbot_component_response_time_seconds"] = {
                        "value": comp_data["response_time"],
                        "labels": {"component": comp_name},
                    }

                metrics["ragbot_component_error_count"] = {
                    "value": comp_data["error_count"],
                    "labels": {"component": comp_name},
                }

            return JSONResponse(content={"metrics": metrics}, status_code=200)

        except Exception as e:
            logger.error(f"Health metrics endpoint failed: {e}")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
                status_code=500,
            )


def create_health_app() -> Optional[Any]:
    """
    Create a standalone FastAPI app for health endpoints.

    Returns:
        FastAPI app instance or None if FastAPI not available
    """
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI not available - cannot create health app")
        return None

    app = FastAPI(
        title="RAGBot Health API",
        description="Health monitoring endpoints for RAGBot",
        version="1.0.0",
    )

    # Initialize health endpoints
    HealthEndpoints(app)

    return app


def start_health_server(port: int = 8081) -> None:
    """
    Start standalone health check server.

    Args:
        port: Port to run the health server on
    """
    if not FASTAPI_AVAILABLE:
        logger.error("Cannot start health server - FastAPI not available")
        return

    try:
        import uvicorn

        app = create_health_app()
        if app is None:
            return

        logger.info(f"Starting health server on port {port}")

        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

    except ImportError:
        logger.error("Cannot start health server - uvicorn not available")
    except Exception as e:
        logger.error(f"Failed to start health server: {e}")
