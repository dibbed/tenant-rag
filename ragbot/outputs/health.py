"""
Health check system for RAGBot components.

This module provides comprehensive health monitoring for all system components
including external services, internal services, and infrastructure.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import requests

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger


class HealthStatus(Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Individual component health status."""

    name: str
    status: HealthStatus
    last_check: datetime
    response_time: Optional[float] = None
    error_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check": self.last_check.isoformat(),
            "response_time": self.response_time,
            "error_count": self.error_count,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class SystemHealth:
    """Overall system health status."""

    overall_status: HealthStatus
    components: Dict[str, ComponentHealth]
    timestamp: datetime
    uptime: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "overall_status": self.overall_status.value,
            "components": {
                name: comp.to_dict() for name, comp in self.components.items()
            },
            "timestamp": self.timestamp.isoformat(),
            "uptime": self.uptime,
        }


class HealthChecker:
    """
    Comprehensive health checker for all system components.

    This class monitors the health of various system components including:
    - External APIs (OpenAI, Anthropic, etc.)
    - Vector stores (FAISS, ChromaDB)
    - Cache services (Redis)
    - Internal services
    """

    def __init__(self) -> None:
        """Initialize health checker."""
        self.start_time = time.time()
        self.component_health: Dict[str, ComponentHealth] = {}
        self.check_interval = settings.monitoring.health_check_interval
        self.running = False
        self._check_task: Optional[asyncio.Task] = None

        logger.info("Health checker initialized", interval=self.check_interval)

    def get_timestamp(self) -> str:
        """Get current timestamp for health status."""
        return datetime.now().isoformat()

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self.running:
            logger.warning("Health monitoring already running")
            return

        self.running = True
        self._check_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop continuous health monitoring."""
        if not self.running:
            return

        self.running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

        logger.info("Health monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.running:
            try:
                await self.check_all_components()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def check_all_components(self) -> SystemHealth:
        """
        Check health of all system components.

        Returns:
            SystemHealth: Overall system health status
        """
        logger.debug("Starting comprehensive health check")

        # Run all health checks concurrently
        check_tasks = [
            self.check_telegram_api(),
            self.check_llm_service(),
            self.check_embedding_service(),
            self.check_vector_store(),
            self.check_cache_service(),
            self.check_file_system(),
            self.check_memory_usage(),
        ]

        # Wait for all checks to complete
        results = await asyncio.gather(*check_tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                component_name = check_tasks[i].__name__.replace("check_", "")
                self.component_health[component_name] = ComponentHealth(
                    name=component_name,
                    status=HealthStatus.UNHEALTHY,
                    last_check=datetime.now(),
                    error_message=str(result),
                    error_count=self.component_health.get(
                        component_name,
                        ComponentHealth(
                            component_name, HealthStatus.UNKNOWN, datetime.now()
                        ),
                    ).error_count
                    + 1,
                )

        # Calculate overall health
        overall_status = self._calculate_overall_health()

        system_health = SystemHealth(
            overall_status=overall_status,
            components=self.component_health.copy(),
            timestamp=datetime.now(),
            uptime=time.time() - self.start_time,
        )

        logger.log_structured(
            "info",
            "health_check_completed",
            overall_status=overall_status.value,
            component_count=len(self.component_health),
            healthy_components=sum(
                1
                for c in self.component_health.values()
                if c.status == HealthStatus.HEALTHY
            ),
            unhealthy_components=sum(
                1
                for c in self.component_health.values()
                if c.status == HealthStatus.UNHEALTHY
            ),
        )

        return system_health

    def _calculate_overall_health(self) -> HealthStatus:
        """Calculate overall system health based on component health."""
        if not self.component_health:
            return HealthStatus.UNKNOWN

        statuses = [comp.status for comp in self.component_health.values()]

        # If any critical component is unhealthy, system is unhealthy
        critical_components = ["llm_service", "vector_store", "telegram_api"]
        for comp_name in critical_components:
            if comp_name in self.component_health:
                if self.component_health[comp_name].status == HealthStatus.UNHEALTHY:
                    return HealthStatus.UNHEALTHY

        # If any component is unhealthy, system is degraded
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.DEGRADED

        # If any component is degraded, system is degraded
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED

        # If all components are healthy, system is healthy
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY

        return HealthStatus.UNKNOWN

    async def check_telegram_api(self) -> ComponentHealth:
        """Check Telegram Bot API health using requests."""
        start_time = time.time()
        component_name = "telegram_api"

        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            # Telegram Bot API getMe endpoint
            url = f"https://api.telegram.org/bot{settings.bot_token}/getMe"

            # Run requests in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor, lambda: requests.get(url, timeout=10)
                )

            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    bot_info = data.get("result", {})

                    health = ComponentHealth(
                        name=component_name,
                        status=HealthStatus.HEALTHY,
                        last_check=datetime.now(),
                        response_time=response_time,
                        metadata={
                            "bot_username": bot_info.get("username"),
                            "bot_id": bot_info.get("id"),
                            "can_join_groups": bot_info.get("can_join_groups"),
                            "can_read_all_group_messages": bot_info.get(
                                "can_read_all_group_messages"
                            ),
                            "first_name": bot_info.get("first_name"),
                            "is_bot": bot_info.get("is_bot"),
                        },
                    )
                else:
                    raise Exception(
                        f"Telegram API error: {data.get('description', 'Unknown error')}"
                    )
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

            self.component_health[component_name] = health
            logger.debug(
                "Telegram API health check passed", response_time=response_time
            )

            return health

        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message="Telegram API timeout - network issue",
            )

            self.component_health[component_name] = health
            logger.error(
                "Telegram API health check failed: timeout", response_time=response_time
            )

            return health

        except requests.exceptions.ConnectionError:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message="Telegram API connection failed - network unreachable",
            )

            self.component_health[component_name] = health
            logger.error(
                "Telegram API health check failed: connection error",
                response_time=response_time,
            )

            return health

        except Exception as e:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message=str(e),
            )

            self.component_health[component_name] = health
            logger.error(
                f"Telegram API health check failed: {e}", response_time=response_time
            )

            return health

    async def check_llm_service(self) -> ComponentHealth:
        """Check LLM service health."""
        start_time = time.time()
        component_name = "llm_service"

        try:
            if settings.llm.provider == "openai":
                await self._check_openai_api()
            elif settings.llm.provider == "anthropic":
                await self._check_anthropic_api()
            elif settings.llm.provider == "ollama":
                await self._check_ollama_api()
            else:
                raise ValueError(f"Unsupported LLM provider: {settings.llm.provider}")

            response_time = time.time() - start_time

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                metadata={
                    "provider": settings.llm.provider,
                    "model": settings.llm.model,
                },
            )

            self.component_health[component_name] = health
            logger.debug(
                "LLM service health check passed",
                provider=settings.llm.provider,
                response_time=response_time,
            )

            return health

        except Exception as e:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message=str(e),
                metadata={
                    "provider": settings.llm.provider,
                    "model": settings.llm.model,
                },
            )

            self.component_health[component_name] = health
            logger.error(
                f"LLM service health check failed: {e}",
                provider=settings.llm.provider,
                response_time=response_time,
            )

            return health

    async def _check_openai_api(self) -> None:
        """Check OpenAI API connectivity."""
        import openai

        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        # Simple API call to check connectivity
        response = await client.chat.completions.create(
            model=settings.llm.model,
            messages=[{"role": "user", "content": "Health check"}],
            max_tokens=5,
            timeout=10.0,
        )

        if not response.choices:
            raise ValueError("No response from OpenAI API")

    async def _check_anthropic_api(self) -> None:
        """Check Anthropic API connectivity."""
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")

        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.llm.model,
            max_tokens=5,
            messages=[{"role": "user", "content": "Health check"}],
        )

        if not response.content or not response.content[0].text:
            raise ValueError("No response from Anthropic API")

    async def _check_ollama_api(self) -> None:
        """Check Ollama API connectivity."""
        import aiohttp

        # Ollama typically runs on localhost:11434
        ollama_url = "http://localhost:11434/api/generate"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                ollama_url,
                json={
                    "model": settings.llm.model,
                    "prompt": "Health check",
                    "stream": False,
                },
                timeout=aiohttp.ClientTimeout(total=10.0),
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Ollama API returned status {response.status}")

    async def check_embedding_service(self) -> ComponentHealth:
        """Check embedding service health."""
        start_time = time.time()
        component_name = "embedding_service"

        try:
            if settings.embedding.provider == "openai":
                await self._check_openai_embeddings()
            elif settings.embedding.provider == "huggingface":
                await self._check_huggingface_embeddings()
            elif settings.embedding.provider == "sentence_transformers":
                await self._check_sentence_transformers()
            else:
                raise ValueError(
                    f"Unsupported embedding provider: {settings.embedding.provider}"
                )

            response_time = time.time() - start_time

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                metadata={
                    "provider": settings.embedding.provider,
                    "model": settings.embedding.model,
                },
            )

            self.component_health[component_name] = health
            logger.debug(
                "Embedding service health check passed",
                provider=settings.embedding.provider,
                response_time=response_time,
            )

            return health

        except Exception as e:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message=str(e),
                metadata={
                    "provider": settings.embedding.provider,
                    "model": settings.embedding.model,
                },
            )

            self.component_health[component_name] = health
            logger.error(
                f"Embedding service health check failed: {e}",
                provider=settings.embedding.provider,
                response_time=response_time,
            )

            return health

    async def _check_openai_embeddings(self) -> None:
        """Check OpenAI embeddings API."""
        import openai

        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        # Simple embedding request
        response = await client.embeddings.create(
            model=settings.embedding.model, input="Health check", timeout=10.0
        )

        if not response.data:
            raise ValueError("No embedding response from OpenAI API")

    async def _check_huggingface_embeddings(self) -> None:
        """Check HuggingFace embeddings."""
        # For HuggingFace, we'll check if the model can be loaded
        try:
            from sentence_transformers import SentenceTransformer

            # This is a lightweight check - just verify model exists
            cache_dir = getattr(
                getattr(settings, "embedding", object()),
                "cache_folder",
                "./cache/sentence_transformers",
            )
            model = SentenceTransformer(
                settings.embedding.model, cache_folder=cache_dir
            )

            # Quick embedding test
            embeddings = model.encode(["Health check"], show_progress_bar=False)

            if len(embeddings) == 0:
                raise ValueError("No embeddings generated")

        except ImportError as err:
            raise ValueError("sentence-transformers library not available") from err

    async def _check_sentence_transformers(self) -> None:
        """Check Sentence Transformers."""
        await self._check_huggingface_embeddings()  # Same implementation

    async def check_vector_store(self) -> ComponentHealth:
        """Check vector store health."""
        start_time = time.time()
        component_name = "vector_store"

        try:
            if settings.vector_db == "faiss":
                await self._check_faiss_store()
            elif settings.vector_db == "chromadb":
                await self._check_chromadb_store()
            elif settings.vector_db == "qdrant":
                await self._check_qdrant_store()
            elif settings.vector_db == "weaviate":
                await self._check_weaviate_store()
            else:
                raise ValueError(f"Unsupported vector database: {settings.vector_db}")

            response_time = time.time() - start_time

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                metadata={
                    "vector_db": settings.vector_db,
                    "store_path": str(settings.store_path),
                },
            )

            self.component_health[component_name] = health
            logger.debug(
                "Vector store health check passed",
                vector_db=settings.vector_db,
                response_time=response_time,
            )

            return health

        except Exception as e:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message=str(e),
                metadata={
                    "vector_db": settings.vector_db,
                    "store_path": str(settings.store_path),
                },
            )

            self.component_health[component_name] = health
            logger.error(
                f"Vector store health check failed: {e}",
                vector_db=settings.vector_db,
                response_time=response_time,
            )

            return health

    async def _check_faiss_store(self) -> None:
        """Check FAISS vector store."""
        try:
            import faiss
            import numpy as np

            # Check if store path exists and is accessible
            if not settings.store_path.exists():
                settings.store_path.mkdir(parents=True, exist_ok=True)

            # Try to create a simple FAISS index to test functionality
            dimension = 384  # Common embedding dimension
            test_index = faiss.IndexFlatL2(dimension)

            # Add a test vector
            test_vector = np.random.random((1, dimension)).astype("float32")
            test_index.add(test_vector)

            # Search to verify functionality
            distances, indices = test_index.search(test_vector, 1)

            if len(indices) == 0:
                raise ValueError("FAISS search returned no results")

        except ImportError as err:
            raise ValueError("FAISS library not available") from err

    async def _check_chromadb_store(self) -> None:
        """Check ChromaDB vector store."""
        try:
            import chromadb

            # Check if store path exists and is accessible
            if not settings.store_path.exists():
                settings.store_path.mkdir(parents=True, exist_ok=True)

            # Try to create a simple ChromaDB client
            client = chromadb.PersistentClient(path=str(settings.store_path))

            # Try to get or create a test collection
            client.get_or_create_collection("health_check")

            # Clean up test collection
            client.delete_collection("health_check")

        except ImportError as err:
            raise ValueError("ChromaDB library not available") from err

    async def _check_qdrant_store(self) -> None:
        """Check Qdrant vector store."""
        try:
            import qdrant_client

            # Check if Qdrant URL is accessible
            url = getattr(settings.store, "qdrant_url", "http://localhost:6333")

            # Try to create a Qdrant client
            client = qdrant_client.QdrantClient(url=url)

            # Try to get collections info
            client.get_collections()

        except ImportError as err:
            raise ValueError("Qdrant client library not available") from err

    async def _check_weaviate_store(self) -> None:
        """Check Weaviate vector store."""
        try:
            import weaviate

            # Check if Weaviate URL is accessible
            url = getattr(settings.store, "weaviate_url", "http://localhost:8080")
            api_key = getattr(settings.store, "weaviate_api_key", None)

            # Try to create a Weaviate client
            client = weaviate.Client(url=url, auth_client_secret=api_key)

            # Try to get schema info
            client.schema.get()

        except ImportError as err:
            raise ValueError("Weaviate client library not available") from err

    async def check_cache_service(self) -> ComponentHealth:
        """Check cache service health."""
        start_time = time.time()
        component_name = "cache_service"

        try:
            if settings.enable_redis:
                await self._check_redis_cache()
            else:
                # Check in-memory cache
                await self._check_memory_cache()

            response_time = time.time() - start_time

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                metadata={
                    "cache_type": "redis" if settings.enable_redis else "memory",
                    "redis_enabled": settings.enable_redis,
                },
            )

            self.component_health[component_name] = health
            logger.debug(
                "Cache service health check passed",
                cache_type="redis" if settings.enable_redis else "memory",
                response_time=response_time,
            )

            return health

        except Exception as e:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message=str(e),
                metadata={
                    "cache_type": "redis" if settings.enable_redis else "memory",
                    "redis_enabled": settings.enable_redis,
                },
            )

            self.component_health[component_name] = health
            logger.error(
                f"Cache service health check failed: {e}",
                cache_type="redis" if settings.enable_redis else "memory",
                response_time=response_time,
            )

            return health

    async def _check_redis_cache(self) -> None:
        """Check Redis cache connectivity."""
        try:
            import redis.asyncio as redis

            # Create Redis client
            redis_client = redis.from_url(
                settings.redis.url,
                max_connections=settings.redis.max_connections,
                socket_timeout=settings.redis.socket_timeout,
            )

            # Test basic operations
            await redis_client.ping()

            # Test set/get operations
            test_key = "health_check_test"
            test_value = "test_value"

            await redis_client.set(test_key, test_value, ex=10)  # 10 second expiry
            retrieved_value = await redis_client.get(test_key)

            if retrieved_value.decode() != test_value:
                raise ValueError("Redis set/get operation failed")

            # Clean up
            await redis_client.delete(test_key)
            await redis_client.close()

        except ImportError as err:
            raise ValueError("Redis library not available") from err

    async def _check_memory_cache(self) -> None:
        """Check in-memory cache functionality."""
        # For in-memory cache, we'll just verify the cache manager is working
        try:
            from ragbot.caching.cache_manager import cache_manager

            # Test basic cache operations
            test_key = "health_check_test"
            test_value = {"test": "value"}

            await cache_manager.set(test_key, test_value, ttl=10)
            retrieved_value = await cache_manager.get(test_key)

            if retrieved_value != test_value:
                raise ValueError("Memory cache set/get operation failed")

            # Clean up
            await cache_manager.delete(test_key)

        except Exception as e:
            raise ValueError(f"Memory cache check failed: {e}") from e

    async def check_file_system(self) -> ComponentHealth:
        """Check file system health."""
        start_time = time.time()
        component_name = "file_system"

        try:
            import os

            # Check if required directories exist and are writable
            directories_to_check = [
                settings.store_path,
                settings.log_file.parent if settings.log_file else None,
            ]

            for directory in directories_to_check:
                if directory is None:
                    continue

                # Ensure directory exists
                directory.mkdir(parents=True, exist_ok=True)

                # Test write permissions
                test_file = directory / "health_check_test.tmp"
                test_file.write_text("test")
                test_file.unlink()  # Clean up

            # Check available disk space
            statvfs = os.statvfs(str(settings.store_path))
            free_space_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)

            response_time = time.time() - start_time

            # Consider degraded if less than 1GB free space
            status = (
                HealthStatus.HEALTHY if free_space_gb > 1.0 else HealthStatus.DEGRADED
            )

            health = ComponentHealth(
                name=component_name,
                status=status,
                last_check=datetime.now(),
                response_time=response_time,
                metadata={
                    "free_space_gb": round(free_space_gb, 2),
                    "store_path_writable": True,
                    "log_path_writable": settings.log_file is not None,
                },
            )

            self.component_health[component_name] = health
            logger.debug(
                "File system health check passed",
                free_space_gb=free_space_gb,
                response_time=response_time,
            )

            return health

        except Exception as e:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message=str(e),
            )

            self.component_health[component_name] = health
            logger.error(
                f"File system health check failed: {e}", response_time=response_time
            )

            return health

    async def check_memory_usage(self) -> ComponentHealth:
        """Check system memory usage."""
        start_time = time.time()
        component_name = "memory_usage"

        try:
            import psutil

            # Get memory information
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory = process.memory_info()

            # Calculate percentages
            system_memory_percent = memory.percent
            process_memory_mb = process_memory.rss / (1024 * 1024)

            response_time = time.time() - start_time

            # Determine status based on memory usage
            if system_memory_percent > 90:
                status = HealthStatus.UNHEALTHY
            elif system_memory_percent > 80:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            health = ComponentHealth(
                name=component_name,
                status=status,
                last_check=datetime.now(),
                response_time=response_time,
                metadata={
                    "system_memory_percent": round(system_memory_percent, 2),
                    "system_memory_available_gb": round(
                        memory.available / (1024**3), 2
                    ),
                    "process_memory_mb": round(process_memory_mb, 2),
                    "process_memory_percent": round(process.memory_percent(), 2),
                },
            )

            self.component_health[component_name] = health
            logger.debug(
                "Memory usage health check passed",
                system_memory_percent=system_memory_percent,
                process_memory_mb=process_memory_mb,
                response_time=response_time,
            )

            return health

        except ImportError:
            # psutil not available, return unknown status
            response_time = time.time() - start_time

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNKNOWN,
                last_check=datetime.now(),
                response_time=response_time,
                error_message="psutil library not available",
            )

            self.component_health[component_name] = health
            logger.warning("Memory usage health check skipped - psutil not available")

            return health

        except Exception as e:
            response_time = time.time() - start_time
            error_count = (
                self.component_health.get(
                    component_name,
                    ComponentHealth(
                        component_name, HealthStatus.UNKNOWN, datetime.now()
                    ),
                ).error_count
                + 1
            )

            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                error_message=str(e),
            )

            self.component_health[component_name] = health
            logger.error(
                f"Memory usage health check failed: {e}", response_time=response_time
            )

            return health

    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of current health status."""
        if not self.component_health:
            return {
                "status": "unknown",
                "message": "No health checks performed yet",
                "components": {},
            }

        overall_status = self._calculate_overall_health()

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "uptime": time.time() - self.start_time,
            "components": {
                name: comp.to_dict() for name, comp in self.component_health.items()
            },
            "summary": {
                "total_components": len(self.component_health),
                "healthy": sum(
                    1
                    for c in self.component_health.values()
                    if c.status == HealthStatus.HEALTHY
                ),
                "degraded": sum(
                    1
                    for c in self.component_health.values()
                    if c.status == HealthStatus.DEGRADED
                ),
                "unhealthy": sum(
                    1
                    for c in self.component_health.values()
                    if c.status == HealthStatus.UNHEALTHY
                ),
                "unknown": sum(
                    1
                    for c in self.component_health.values()
                    if c.status == HealthStatus.UNKNOWN
                ),
            },
        }


# Global health checker instance
health_checker = HealthChecker()
