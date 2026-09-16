"""
Package entry point to start the Telegram bot.

This mirrors the repository root `main.py` so the console script
`ragbot` defined in pyproject works as expected.
"""

from __future__ import annotations

import asyncio
import sys

from ragbot.app.bot import main as bot_main
from ragbot.configs.settings import settings
from ragbot.monitoring.health_checker import HealthChecker
from ragbot.monitoring.real_time_monitor import RealTimeMonitor
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import (
    get_integration_service,
    shutdown_integration_service,
)
from ragbot.utils.signal_handler import GracefulShutdown


async def _run_async() -> None:
    shutdown_manager = GracefulShutdown()

    with shutdown_manager:
        try:
            logger.info("Starting RAG Telegram Assistant (package entry)...")
            logger.info(
                "Loaded settings",
                default_lang=settings.default_lang,
                llm_provider=settings.llm.provider,
                embed_provider=settings.embedding.provider,
            )

            integration_service = await get_integration_service()
            logger.info("Integration service initialized")

            _ = await integration_service.get_rag_service()
            logger.info("RAG service ready")

            health_status = await integration_service.health_check()
            logger.info(f"System health: {health_status.get('status', 'unknown')}")

            # Initialize monitoring components
            monitor: RealTimeMonitor | None = None
            checker: HealthChecker | None = None
            try:
                if settings.monitoring.enable_real_time_monitoring:
                    monitor = RealTimeMonitor(
                        check_interval=settings.monitoring.monitoring_interval
                    )
                    # Apply thresholds from settings if provided
                    monitor.alert_thresholds.update(
                        settings.monitoring.alert_thresholds or {}
                    )
                    await monitor.start_monitoring()
                    logger.info(
                        "Real-time monitoring started",
                        interval=settings.monitoring.monitoring_interval,
                    )

                # Start periodic health checks
                checker = HealthChecker()
                checker.check_interval = settings.monitoring.health_check_interval
                if settings.monitoring.health_check_interval > 0:
                    # Run one round eagerly to populate initial status; background loop stays in its method if started elsewhere
                    await checker._run_all_checks()  # internal call intentional
                    logger.info("Initial health checks completed")
            except Exception as mon_exc:
                logger.warning(f"Monitoring init warning: {mon_exc}")

            await bot_main(shutdown_manager)
        finally:
            try:
                # Add timeout for shutdown
                await asyncio.wait_for(shutdown_integration_service(), timeout=10.0)
                logger.info("Application shutdown completed")
            except asyncio.TimeoutError:
                logger.warning("Shutdown timeout reached, forcing exit...")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")


def main() -> None:
    """Synchronous console entry that runs the async runner."""
    try:
        asyncio.run(_run_async())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
