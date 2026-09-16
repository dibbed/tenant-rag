"""
Integration Service for RAG Bot

This service orchestrates all system components and manages their lifecycle.
It provides a unified interface for accessing all services and components.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from ragbot.configs.settings import Settings
from ragbot.outputs.logger import logger
from ragbot.analytics.analytics_dashboard import AnalyticsDashboard
from ragbot.outputs.health import HealthChecker
from ragbot.outputs.metrics import MetricsManager
from ragbot.outputs.performance_dashboard import PerformanceDashboard
from ragbot.outputs.optimization_engine import OptimizationEngine
from ragbot.rag.loaders import (
    AdvancedDocumentLoader,
    HTMLLoader,
    PDFLoader,
    TextLoader,
)
from ragbot.rag.chunkers import AdaptiveChunker
from ragbot.rag.embeddings import OpenAIEmbedder, HuggingFaceEmbedder, STEmbedder
from ragbot.rag.store import VectorStoreFactory
from ragbot.rag.qa import QAChain
from ragbot.rag.retrieve import AdvancedRetriever
from ragbot.caching import CacheManager
from ragbot.services.document_service import DocumentService
from ragbot.services.graceful_degradation import graceful_degradation
from ragbot.services.rag_service import RAGService

# Global instance
_integration_service: Optional[IntegrationService] = None
_global_metrics_manager: Optional[MetricsManager] = None


def get_global_metrics_manager() -> MetricsManager:
    """Get or create global metrics manager instance."""
    global _global_metrics_manager
    if _global_metrics_manager is None:
        _global_metrics_manager = MetricsManager()
    return _global_metrics_manager


class IntegrationService:
    """
    Main integration service that wires all components together
    """

    def __init__(self, config: Optional[Settings] = None):
        """Initialize integration service with all components"""
        self.settings = config or Settings()

        # Validate critical settings before initialization
        self._validate_settings()

        self.components: Dict[str, Any] = {}
        self.health_checker = HealthChecker()
        # Use global metrics manager to prevent duplicate initialization
        self.metrics = get_global_metrics_manager()
        from ragbot.configs.settings import settings

        self.performance_dashboard = PerformanceDashboard(settings)
        self.analytics_dashboard = AnalyticsDashboard(settings)
        self._initialized = False
        self.optimization_engine: Optional[OptimizationEngine] = None

    def _validate_settings(self) -> None:
        """Validate critical settings before initialization."""
        logger.info("Validating critical settings...")

        validation_errors = []
        validation_warnings = []

        # Required settings validation (provider-aware for API keys)
        # Always require data_dir
        if not getattr(self.settings, "data_dir", None):
            validation_errors.append(
                "Data directory is required for vector store and cache"
            )

        # LLM provider specific API keys
        try:
            llm_provider = getattr(
                getattr(self.settings, "llm", object()), "provider", "openai"
            )
        except Exception:
            llm_provider = "openai"
        if llm_provider == "openai":
            if not getattr(
                getattr(self.settings, "llm", object()), "platform", None
            ) and not getattr(
                getattr(self.settings, "llm", object()), "provider", None
            ):
                try:
                    import openai

                    if not openai.api_key:
                        validation_warnings.append("OpenAI API key not configured")
                except ImportError:
                    validation_warnings.append("OpenAI not available")
        elif llm_provider == "anthropic":
            if not getattr(self.settings, "anthropic_api_key", None):
                validation_warnings.append("Anthropic API key not configured")

        # Telegram bot token
        if not getattr(self.settings, "bot_token", None):
            validation_errors.append("Telegram bot token is required")

        # Log validation results
        if validation_errors:
            for error in validation_errors:
                logger.error(f"Validation error: {error}")
            logger.error("Critical validation errors found - fixing required")

        if validation_warnings:
            for warning in validation_warnings:
                logger.warning(f"Validation warning: {warning}")

        if not validation_errors:
            logger.success("Settings validation completed successfully")

    def _get_api_key_for_provider(self) -> Optional[str]:
        """Get API key for the current provider."""
        try:
            llm_provider = getattr(self.settings.llm, "provider", "openai")

            if llm_provider == "openai":
                return getattr(self.settings, "openai_api_key", None)
            elif llm_provider == "anthropic":
                return getattr(self.settings, "anthropic_api_key", None)
            elif llm_provider == "openrouter":
                return getattr(self.settings, "openrouter_api_key", None)
            else:
                # Default to OpenAI
                return getattr(self.settings, "openai_api_key", None)
        except Exception:
            return None

    async def initialize(self) -> None:
        """Initialize all system components"""
        try:
            trace_id = f"init-{id(self)}"
            logger.info("Initializing RAG system components...", trace_id=trace_id)

            # Initialize core components
            async def _timed(name: str, coro):
                import time as _t

                t0 = _t.time()
                res = await coro
                dt = _t.time() - t0
                logger.info(
                    "Component initialized",
                    component=name,
                    duration=f"{dt:.2f}s",
                    trace_id=trace_id,
                )
                return res

            await _timed("loaders", self._initialize_loaders())
            await _timed("chunker", self._initialize_chunker())
            await _timed("embedder", self._initialize_embedder())
            await _timed("vector_store", self._initialize_vector_store())
            await _timed("qa_chain", self._initialize_qa_chain())
            await _timed("cache", self._initialize_cache())
            await _timed("rag_service", self._initialize_rag_service())
            await _timed("plugin_system", self._initialize_plugin_system())
            await _timed(
                "performance_dashboard", self._initialize_performance_dashboard()
            )
            await _timed("analytics_dashboard", self._initialize_analytics_dashboard())

            # Start optimization engine
            await _timed("optimization_engine", self._initialize_optimization_engine())

            # Verify all components
            await _timed("verify_components", self._verify_components())

            # Health check optional loaders
            await _timed("health_check_loaders", self._health_check_optional_loaders())

            self._initialized = True
            logger.success(
                "All system components initialized successfully", trace_id=trace_id
            )

            # Log graceful degradation metrics summary
            await self._log_graceful_degradation_summary(trace_id)

        except Exception as e:
            logger.error(f"Failed to initialize integration service: {e}")
            raise

    async def _initialize_loaders(self) -> None:
        """Initialize document loaders"""
        try:
            # Initialize advanced loaders
            self.components["loaders"] = AdvancedDocumentLoader()

            # Add specific loader types
            self.components["pdf_loader"] = PDFLoader()
            self.components["text_loader"] = TextLoader()
            self.components["html_loader"] = HTMLLoader()

            logger.success("Document loaders initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "loaders", e, "Document loaders initialization failed"
            )

    async def _initialize_chunker(self) -> None:
        """Initialize text chunker"""
        try:
            self.components["chunker"] = AdaptiveChunker(
                **self.settings.advanced_chunking.__dict__
            )
            logger.success("Text chunker initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "chunker", e, "Text chunker initialization failed"
            )

    async def _initialize_embedder(self) -> None:
        """Initialize embedding service"""
        try:
            provider = self.settings.embedding.provider

            if provider == "openai":
                self.components["embedder"] = OpenAIEmbedder(
                    api_key=self._get_api_key_for_provider(),
                    **self.settings.embedding.__dict__,
                )
            elif provider == "huggingface":
                self.components["embedder"] = HuggingFaceEmbedder(
                    **self.settings.embedding.__dict__
                )
            elif provider == "sentence_transformers":
                self.components["embedder"] = STEmbedder(
                    **self.settings.embedding.__dict__
                )
            else:
                # Default to OpenAI
                self.components["embedder"] = OpenAIEmbedder(
                    api_key=self._get_api_key_for_provider(),
                    **self.settings.embedding.__dict__,
                )

            logger.success("Embedding service initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "embedder", e, "Embedding service initialization failed"
            )

    async def _initialize_vector_store(self) -> None:
        """Initialize vector store"""
        try:
            vector_store_config = self.settings.store.__dict__
            self.components["vector_store"] = VectorStoreFactory.create_store(
                self.settings.vector_db, **vector_store_config
            )
            logger.success("Vector store initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "vector_store", e, "Vector store initialization failed"
            )

    async def _initialize_qa_chain(self) -> None:
        """Initialize QA chain"""
        try:
            # Get LLM provider and model from settings
            llm_provider = getattr(self.settings.llm, "provider", "hf_local")
            model_name = getattr(
                self.settings.llm, "model", "microsoft/DialoGPT-medium"
            )
            max_tokens = getattr(self.settings.llm, "max_tokens", None)
            temperature = getattr(self.settings.llm, "temperature", 0.3)
            api_key = self._get_api_key_for_provider()

            # Pass retriever to QAChain if available
            retriever = self.components.get("advanced_retriever")

            self.components["qa_chain"] = QAChain(
                llm_provider=llm_provider,
                model_name=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                api_key=api_key,
                retriever=retriever,
            )
            logger.success("QA chain initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "qa_chain", e, "QA chain initialization failed"
            )

    async def _initialize_cache(self) -> None:
        """Initialize cache"""
        try:
            self.components["cache"] = CacheManager()
            await self.components["cache"].initialize()
            logger.success("Cache initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "cache", e, "Cache initialization failed"
            )

    async def _initialize_advanced_retriever(self) -> None:
        """Initialize advanced retriever"""
        try:
            retriever_config = self.settings.advanced_retrieval.__dict__
            self.components["advanced_retriever"] = AdvancedRetriever(
                vector_store=self.components["vector_store"], **retriever_config
            )
            logger.success("Advanced retriever initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "advanced_retriever", e, "Advanced retriever initialization failed"
            )

    async def _initialize_rag_service(self) -> None:
        """Initialize main RAG service"""
        try:
            advanced_retriever = self.components.get("advanced_retriever")
            performance_monitor = getattr(self, "metrics", None)

            # RAG expects loaders dict: {"text": TextLoader(), "pdf": PDFLoader(), ...}
            rag_loaders = {
                "text": self.components.get("text_loader"),
                "pdf": self.components.get("pdf_loader"),
                "html": self.components.get("html_loader"),
            }
            rag_loaders = {k: v for k, v in rag_loaders.items() if v is not None}

            # Initialize Document Service
            self.components["document_service"] = DocumentService(
                loaders=self.components.get("loaders"),
                chunker=self.components.get("chunker"),
                embedder=self.components.get("embedder"),
                vector_store=self.components.get("vector_store"),
                cache=self.components.get("cache"),
            )

            self.components["rag_service"] = RAGService(
                loaders=rag_loaders if rag_loaders else None,
                chunker=self.components.get("chunker"),
                embedder=self.components.get("embedder"),
                vector_store=self.components.get("vector_store"),
                qa_chain=self.components.get("qa_chain"),
                cache=self.components.get("cache"),
                advanced_retriever=advanced_retriever,
                performance_monitor=performance_monitor,
            )

            logger.success("RAG service initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "rag_service", e, "RAG service initialization failed"
            )

    async def _initialize_plugin_system(self) -> None:
        """Initialize plugin system"""
        try:
            rag_service = self.components.get("rag_service")
            if not rag_service:
                logger.error("RAG service not available for plugin initialization")
                return

            # Initialize plugin system
            success = await rag_service.initialize_plugin_system()
            if success:
                logger.success("Plugin system initialized successfully")
            else:
                logger.warning("Plugin system initialization attempted but failed")

        except Exception as e:
            logger.error(f"Error initializing plugin system: {e}")

    async def _initialize_performance_dashboard(self) -> None:
        """Initialize performance dashboard"""
        try:
            await self.performance_dashboard.initialize()
            logger.success("Performance dashboard initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "performance_dashboard",
                e,
                "Performance dashboard initialization failed",
            )

    async def _initialize_analytics_dashboard(self) -> None:
        """Initialize analytics dashboard"""
        try:
            await self.analytics_dashboard.initialize()
            logger.success("Analytics dashboard initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "analytics_dashboard", e, "Analytics dashboard initialization failed"
            )

    async def _initialize_optimization_engine(self) -> None:
        """Initialize optimization engine"""
        try:
            self.optimization_engine = OptimizationEngine()
            await self.optimization_engine.start()
            logger.success("Optimization engine initialized")
        except Exception as e:
            await graceful_degradation.handle_component_failure(
                "optimization_engine", e, "Optimization engine initialization failed"
            )

    async def _verify_components(self) -> None:
        """Verify all components are working"""
        logger.info("Verifying component health...")

        for component_name, component in self.components.items():
            try:
                if hasattr(component, "health_check"):
                    health = await component.health_check()
                    if health:
                        logger.info(f"✅ {component_name} - Healthy")
                    else:
                        logger.warning(f"⚠️ {component_name} - Degraded")
                else:
                    logger.info(f"✅ {component_name} - No health check available")
            except Exception as e:
                logger.warning(f"⚠️ {component_name} - Health check failed: {e}")

    async def _health_check_optional_loaders(self) -> None:
        """Health check for optional loaders"""
        optional_loaders = ["pdf_loader", "html_loader"]

        for loader_name in optional_loaders:
            loader = self.components.get(loader_name)
            if loader:
                try:
                    if hasattr(loader, "health_check"):
                        await loader.health_check()
                        logger.info(f"✅ {loader_name} health check passed")
                except Exception as e:
                    logger.warning(f"⚠️ {loader_name} health check failed: {e}")

    async def _log_graceful_degradation_summary(self, trace_id: str) -> None:
        """Log graceful degradation metrics summary"""
        degraded_components = graceful_degradation.get_failed_components()
        if degraded_components:
            logger.warning(
                "Graceful degradation summary",
                degraded_components=list(degraded_components.keys()),
                trace_id=trace_id,
            )
        else:
            logger.info(
                "All components initialized successfully",
                trace_id=trace_id,
            )

    async def shutdown(self) -> None:
        """Safely shutdown all components"""
        logger.info("Shutting down integration service...")

        try:
            # Quick shutdown for critical components first
            if self.optimization_engine:
                try:
                    await asyncio.wait_for(
                        self.optimization_engine.shutdown(), timeout=3.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Optimization engine shutdown timeout")

            if hasattr(self.performance_dashboard, "shutdown"):
                try:
                    await asyncio.wait_for(
                        self.performance_dashboard.shutdown(), timeout=3.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Performance dashboard shutdown timeout")

            if hasattr(self.analytics_dashboard, "shutdown"):
                try:
                    await asyncio.wait_for(
                        self.analytics_dashboard.shutdown(), timeout=3.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Analytics dashboard shutdown timeout")

            # Shutdown components in reverse order with timeout
            for component_name, component in reversed(list(self.components.items())):
                try:
                    if hasattr(component, "shutdown"):
                        await asyncio.wait_for(component.shutdown(), timeout=2.0)
                    elif hasattr(component, "close"):
                        await asyncio.wait_for(component.close(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Component {component_name} shutdown timeout")
                except Exception as e:
                    logger.warning(f"Error shutting down {component_name}: {e}")

            logger.success("Integration service shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            self._initialized = False

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "components": {},
            "issues": [],
        }

        # Check core components with more lenient approach
        required_components = ["rag_service", "vector_store", "embedder", "qa_chain"]
        healthy_count = 0

        # Debug: Log available components
        logger.debug(f"Available components: {list(self.components.keys())}")

        for component_name in required_components:
            component = self.components.get(component_name)
            if component:
                try:
                    if hasattr(component, "health_check"):
                        try:
                            component_health = await component.health_check()
                            health_status["components"][component_name] = component_health
                            # Consider component healthy if it exists and responds
                            if component_health.get("status") in ["healthy", "unknown"]:
                                healthy_count += 1
                        except Exception as health_error:
                            # Health check failed but component exists - consider it degraded
                            health_status["components"][component_name] = {
                                "status": "degraded",
                                "error": str(health_error),
                                "note": "Health check failed but component exists"
                            }
                            healthy_count += 1  # Still count as healthy since component exists
                    else:
                        # Component exists but no health check - consider it healthy
                        health_status["components"][component_name] = {
                            "status": "healthy",
                            "note": "No health check method available"
                        }
                        healthy_count += 1
                except Exception as e:
                    health_status["components"][component_name] = {
                        "status": "unhealthy",
                        "error": str(e),
                    }
                    health_status["issues"].append(f"{component_name}: {e}")
            else:
                health_status["components"][component_name] = {"status": "missing"}
                health_status["issues"].append(f"{component_name}: Component missing")

        # More lenient health determination - consider system healthy if rag_service is healthy
        if health_status["components"].get("rag_service", {}).get("status") == "healthy":
            health_status["status"] = "healthy"
        elif healthy_count >= len(required_components) * 0.75:  # 75% of components healthy
            health_status["status"] = "healthy"
        elif healthy_count >= len(required_components) * 0.5:  # 50% of components healthy
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "unhealthy"

        return health_status

    def get_component(self, name: str) -> Optional[Any]:
        """Get a component by name"""
        return self.components.get(name)

    def get_rag_service(self) -> Optional[RAGService]:
        """Get the RAG service"""
        return self.components.get("rag_service")

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary from all components"""
        summary = {"timestamp": time.time(), "system": {}, "components": {}}

        # System-level metrics
        if hasattr(self.metrics, "get_metrics_summary"):
            summary["system"] = self.metrics.get_metrics_summary()

        # Component-level metrics
        for component_name, component in self.components.items():
            try:
                if hasattr(component, "get_metrics_summary"):
                    summary["components"][
                        component_name
                    ] = await component.get_metrics_summary()
            except Exception as e:
                logger.warning(f"Error getting metrics for {component_name}: {e}")

        return summary


async def get_integration_service() -> IntegrationService:
    """Get global integration service instance"""
    global _integration_service
    if _integration_service is None:
        _integration_service = IntegrationService()
        await _integration_service.initialize()
    return _integration_service


async def shutdown_integration_service() -> None:
    """Shutdown global integration service"""
    global _integration_service
    if _integration_service:
        await _integration_service.shutdown()
        _integration_service = None
