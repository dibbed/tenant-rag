"""
Package entry point to start the RAGBot HTTP API server.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path when invoked directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ragbot.outputs.logger import logger


def main() -> None:
    """Launch the RAGBot FastAPI application server using Uvicorn."""
    parser = argparse.ArgumentParser(
        prog="ragbot",
        description="RAGBot API Server - Production-ready Retrieval-Augmented Generation HTTP API",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host IP to bind the HTTP server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port to bind the HTTP server to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("RELOAD", "false").lower() == "true",
        help="Enable auto-reload for local development",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("WORKERS", "1")),
        help="Number of worker processes (default: 1)",
    )

    args, _ = parser.parse_known_args()

    logger.info(
        f"Starting RAGBot API server on {args.host}:{args.port} (workers: {args.workers})"
    )

    try:
        uvicorn.run(
            "ragbot.api.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,
        )
    except KeyboardInterrupt:
        logger.info("RAGBot API server stopped by user")
    except Exception as exc:
        logger.error(f"Failed to start RAGBot API server: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
