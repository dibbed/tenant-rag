#!/usr/bin/env python3
"""
RAG Telegram Assistant - Main Entry Point
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Only reload settings if explicitly requested
if os.getenv("RAGBOT_RELOAD_SETTINGS", "false").lower() == "true":
    if "ragbot.configs.settings" in sys.modules:
        del sys.modules["ragbot.configs.settings"]

from ragbot.app.bot import main as bot_main
from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import get_integration_service
from ragbot.utils.signal_handler import GracefulShutdown


async def main():
    """Main application entry point"""
    shutdown_manager = GracefulShutdown()

    with shutdown_manager:
        try:
            logger.info("Starting RAG Telegram Assistant...")

            # Load settings context
            logger.info(
                "Loaded settings",
                default_lang=settings.default_lang,
                llm_provider=settings.llm.provider,
                embed_provider=settings.embedding.provider,
            )

            # Initialize integration service
            integration_service = await get_integration_service()
            logger.info("Integration service initialized")

            # Get RAG service
            rag_service = integration_service.get_rag_service()
            if rag_service:
                logger.info("RAG service ready")
            else:
                logger.warning(
                    "RAG service not available, continuing with limited functionality"
                )

            # Health check
            health_status = await integration_service.health_check()
            logger.info(f"System health: {health_status['status']}")

            if health_status["status"] != "healthy":
                logger.warning("System is not fully healthy, but continuing...")

            logger.info("RAG Telegram Assistant started successfully!")
            logger.info("Starting Telegram bot...")

            # Start the Telegram bot with shutdown awareness
            await bot_main(shutdown_manager)

        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            raise
        finally:
            # Cleanup with timeout
            try:
                from ragbot.services.integration_service import (
                    shutdown_integration_service,
                )

                # Add timeout for shutdown
                await asyncio.wait_for(shutdown_integration_service(), timeout=10.0)
                logger.info("Application shutdown completed")
            except asyncio.TimeoutError:
                logger.warning("Shutdown timeout reached, forcing exit...")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)
