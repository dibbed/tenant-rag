"""
RAG Service Orchestrator.

This module provides the main service class for coordinating RAG operations,
including document ingestion, query processing, and health monitoring.
"""

import asyncio
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.rag.exceptions import (
    DocumentProcessingError,
    EmbeddingError,
    LLMError,
)
from ragbot.rag.error_handling import (
    ErrorContext,
)
from ragbot.rag import (
    Document,
    VectorDocument,
    QueryAggregator,
    AdvancedFilter,
    CustomScorer,
    QueryOptimizer,
)
from ragbot.security import EncryptionManager, KeyManager, SecureBackupManager
from ragbot.services.document_service import DocumentService
from ragbot.analytics import AnalyticsDashboard
from ragbot.utils.debug_helpers import log_pydantic_error
from ragbot.multi_tenant import TenantManager, TenantAuth, TenantAnalytics
from ragbot.multi_tenant.models import TenantTier, TenantPlan, TenantStatus
from ragbot.plugins import (
    PluginManager,
    BasePlugin,
    PluginContext,
    PluginResult,
    PluginStatus as PluginStatusEnum,
    HookType,
)


@dataclass
class IngestResult:
    """Result of document ingestion operation."""

    success: bool
    document_id: str
    chunks_created: int
    processing_time: float
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class QueryResult:
    """Result of query operation."""

    answer: str
    sources: List[str]
    confidence_score: float
    processing_time: float
    language: str
    retrieved_chunks: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ComponentHealth:
    """Individual component health status."""

    status: str
    last_check: datetime
    error_count: int
    response_time: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class HealthStatus:
    """System health status."""

    overall_status: str
    components: Dict[str, ComponentHealth]
    timestamp: datetime
    uptime: float
    document_count: int
    last_query_time: Optional[datetime] = None


class RAGService:
    """
    Main service orchestrating RAG operations.

    This service coordinates document ingestion, query processing, and provides
    health monitoring for the entire RAG pipeline.
    """

    def __init__(
        self,
        loaders=None,
        chunker=None,
        embedder=None,
        vector_store=None,
        qa_chain=None,
        cache=None,
        advanced_retriever=None,
        semantic_cache=None,
        performance_monitor=None,
        document_service=None,
        config=None,
        **kwargs: Any,
    ) -> None:
        """Initialize the RAG service with provided components."""
        self.config = config
        self.extra_kwargs = kwargs
        self.start_time = datetime.now()
        self.performance_monitor = performance_monitor
        self.last_query_time: Optional[datetime] = None
        self.component_error_counts: Dict[str, int] = {
            "loader": 0,
            "chunker": 0,
            "embedder": 0,
            "vector_store": 0,
            "retriever": 0,
            "qa_chain": 0,
            "semantic_cache": 0,
        }

        # Advanced metrics tracking
        self.metrics_history: Dict[str, List[float]] = {
            "query_duration": [],
            "ingest_duration": [],
            "embedding_duration": [],
            "retrieval_duration": [],
            "qa_duration": [],
        }
        self.request_counts: Dict[str, int] = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_ingests": 0,
            "successful_ingests": 0,
            "failed_ingests": 0,
        }

        # Initialize components with error handling
        try:
            self.loaders = loaders or self._initialize_default_loaders()
        except Exception as e:
            logger.warning(f"Failed to initialize loaders: {e}")
            self.loaders = None

        try:
            self.chunker = chunker or self._initialize_default_chunker()
        except Exception as e:
            logger.warning(f"Failed to initialize chunker: {e}")
            self.chunker = None

        try:
            self.embedder = embedder or self._initialize_default_embedder()
        except Exception as e:
            logger.warning(f"Failed to initialize embedder: {e}")
            self.embedder = None

        try:
            self.vector_store = vector_store or self._initialize_default_vector_store()
        except Exception as e:
            logger.warning(f"Failed to initialize vector store: {e}")
            self.vector_store = None

        try:
            self.qa_chain = qa_chain or self._initialize_default_qa_chain()
            logger.info("QA chain component initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize QA chain: {e}", exc_info=True)
            self.qa_chain = None

        self.cache = cache

        try:
            self.advanced_retriever = (
                advanced_retriever or self._initialize_advanced_retriever()
            )
        except Exception as e:
            logger.warning(f"Failed to initialize advanced retriever: {e}")
            self.advanced_retriever = None

        try:
            if semantic_cache is not None:
                self.semantic_cache = semantic_cache
            elif cache is not None and getattr(cache, "semantic_cache", None) is not None:
                self.semantic_cache = cache.semantic_cache
            else:
                self.semantic_cache = self._initialize_semantic_cache()
        except Exception as e:
            logger.warning(f"Failed to initialize semantic cache: {e}")
            self.semantic_cache = None

        try:
            self.document_service = (
                document_service or self._initialize_document_service()
            )
        except Exception as e:
            logger.warning(f"Failed to initialize document service: {e}")
            self.document_service = None

        # Initialize security components
        self.encryption_manager = EncryptionManager()
        self.key_manager = KeyManager()
        self.backup_manager = SecureBackupManager(self.encryption_manager)

        # Initialize query components with vector store (if available)
        if self.vector_store:
            try:
                self.query_aggregator = QueryAggregator(self.vector_store)
                self.advanced_filter = AdvancedFilter(self.vector_store)
                self.custom_scorer = CustomScorer(self.vector_store)
                self.query_optimizer = QueryOptimizer(self.vector_store)
            except Exception as e:
                logger.warning(f"Failed to initialize query components: {e}")
                self.query_aggregator = None
                self.advanced_filter = None
                self.custom_scorer = None
                self.query_optimizer = None
        else:
            self.query_aggregator = None
            self.advanced_filter = None
            self.custom_scorer = None
            self.query_optimizer = None

        # Initialize analytics dashboard
        self.analytics_dashboard = AnalyticsDashboard(settings)

        # Multi-tenant vector store and retriever isolation caches
        self._tenant_vector_stores: Dict[str, Any] = {}
        self._tenant_retrievers: Dict[str, Any] = {}

        # Initialize multi-tenant components
        if getattr(settings, "enable_multi_tenant", False) or getattr(
            getattr(settings, "multi_tenant", object()), "enabled", False
        ):
            self.tenant_manager = TenantManager(settings)
            self.tenant_auth = TenantAuth(self.tenant_manager)
            self.tenant_analytics = TenantAnalytics(self.tenant_manager)
        else:
            self.tenant_manager = None
            self.tenant_auth = None
            self.tenant_analytics = None

        # Initialize plugin system
        self.plugin_manager = self._initialize_plugin_manager()

        logger.info("RAG service initialized successfully")

        # Log component status
        logger.info(
            "RAG service component status",
            loaders=bool(self.loaders),
            chunker=bool(self.chunker),
            embedder=bool(self.embedder),
            vector_store=bool(self.vector_store),
            qa_chain=bool(self.qa_chain),
            cache=bool(self.cache),
            advanced_retriever=bool(self.advanced_retriever),
            semantic_cache=bool(self.semantic_cache),
            document_service=bool(self.document_service),
            tenant_manager=bool(self.tenant_manager),
            plugin_manager=bool(self.plugin_manager),
        )

    def get_vector_store(self, tenant_id: Optional[str] = None):
        """Get vector store for a specific tenant or the default vector store."""
        if not tenant_id:
            return self.vector_store

        if tenant_id in self._tenant_vector_stores:
            return self._tenant_vector_stores[tenant_id]

        if not (
            getattr(settings, "enable_multi_tenant", False)
            or getattr(getattr(settings, "multi_tenant", object()), "enabled", False)
        ):
            return self.vector_store

        from ragbot.rag.store.factory import VectorStoreFactory
        from pathlib import Path

        provider = str(getattr(settings, "vector_db", "faiss")).lower()
        cfg = getattr(settings, "store", object())
        vector_store_cfg = getattr(settings, "vector_store", object())

        base_kwargs = {
            "similarity_metric": getattr(cfg, "similarity_metric", "cosine"),
            "config": vector_store_cfg,
        }

        if provider == "faiss":
            base_store_path = Path(
                getattr(cfg, "store_path", None) or str(settings.store_path)
            )
            tenant_store_path = str(base_store_path / "tenants" / tenant_id)
            base_kwargs.update(
                {
                    "store_path": tenant_store_path,
                    "faiss_nlist": getattr(cfg, "faiss_nlist", 0),
                    "faiss_nprobe": getattr(cfg, "faiss_nprobe", 0),
                    "faiss_hnsw_m": getattr(cfg, "faiss_hnsw_m", 0),
                    "faiss_hnsw_ef_search": getattr(cfg, "faiss_hnsw_ef_search", 0),
                    "keep_embeddings": getattr(cfg, "store_keep_embeddings", True),
                }
            )
        elif provider in ("chroma", "chromadb"):
            default_chroma_path = str(settings.store_path / "chroma")
            base_kwargs.update(
                {
                    "persist_directory": getattr(
                        cfg, "chroma_persist_directory", default_chroma_path
                    ),
                    "collection_name": f"tenant_{tenant_id}",
                    "distance_function": getattr(
                        cfg, "chroma_distance_function", "cosine"
                    ),
                }
            )
        elif provider == "qdrant":
            default_qdrant_path = str(settings.store_path / "qdrant")
            base_kwargs.update(
                {
                    "url": getattr(cfg, "qdrant_url", "http://localhost:6333"),
                    "path": getattr(cfg, "qdrant_path", default_qdrant_path),
                    "collection_name": f"tenant_{tenant_id}",
                    "vector_size": getattr(cfg, "qdrant_vector_size", 1536),
                    "timeout": getattr(cfg, "qdrant_timeout", 30),
                }
            )
        else:
            base_kwargs["collection_name"] = f"tenant_{tenant_id}"

        try:
            store = VectorStoreFactory.create_store(provider, **base_kwargs)
            self._tenant_vector_stores[tenant_id] = store
            return store
        except Exception as e:
            logger.error(f"Failed to create vector store for tenant {tenant_id}: {e}")
            return self.vector_store

    def get_retriever(self, tenant_id: Optional[str] = None):
        """Get advanced retriever instance (default or tenant-specific)."""
        if not tenant_id or not getattr(
            getattr(settings, "multi_tenant", object()), "enabled", False
        ):
            return self.advanced_retriever

        if tenant_id in self._tenant_retrievers:
            return self._tenant_retrievers[tenant_id]

        tenant_store = self.get_vector_store(tenant_id)
        if not tenant_store:
            return self.advanced_retriever

        try:
            from ragbot.rag.retrieve.advanced_retriever import AdvancedRetriever

            adv_settings = getattr(settings, "advanced_retrieval", object())
            retriever = AdvancedRetriever(
                vector_store=tenant_store,
                embedder=self.embedder,
                enable_reranking=getattr(adv_settings, "enable_reranking", False),
                enable_hybrid=getattr(
                    adv_settings, "enable_hybrid", getattr(adv_settings, "enable_hybrid_search", False)
                ),
                enable_expansion=getattr(
                    adv_settings,
                    "enable_expansion",
                    getattr(adv_settings, "enable_query_expansion", False),
                ),
                reranker_model=getattr(adv_settings, "reranker_model", None),
                reranker_threshold=getattr(adv_settings, "reranker_threshold", None),
                hybrid_alpha=getattr(adv_settings, "hybrid_alpha", None),
                keyword_search_enabled=getattr(adv_settings, "keyword_search_enabled", None),
            )
            self._tenant_retrievers[tenant_id] = retriever
            return retriever
        except Exception as e:
            logger.warning(f"Failed to create tenant retriever for {tenant_id}: {e}")
            return self.advanced_retriever

    def _initialize_plugin_manager(self):
        """Initialize plugin manager"""
        try:
            from ragbot.plugins import PluginManager

            plugin_dir = getattr(
                getattr(settings, "plugins", object()), "plugin_directory", None
            ) or str(getattr(settings, "plugin_directory", "plugins"))
            plugin_manager = PluginManager(plugin_directory=str(plugin_dir))
            logger.info("Plugin manager initialized")
            return plugin_manager
        except Exception as e:
            logger.error(f"Failed to initialize plugin manager: {e}")
            return None

    async def initialize_plugin_system(self) -> bool:
        """Initialize and auto-load plugins if enabled"""
        try:
            if not self.plugin_manager:
                logger.warning("Plugin manager not available")
                return False

            success = await self.plugin_manager.initialize()
            if success:
                logger.info("Plugin system initialized successfully")
                auto_load = getattr(
                    getattr(settings, "plugins", object()),
                    "auto_load",
                    getattr(settings, "auto_load_plugins", False),
                )
                if auto_load:
                    logger.info("Auto-loading plugins...")
                    loaded_plugins = (
                        await self.plugin_manager.load_plugins_from_directory()
                    )
                    logger.info(f"Auto-loaded {len(loaded_plugins)} plugins")
                return True
            else:
                logger.error("Failed to initialize plugin system")
                return False
        except Exception as e:
            logger.error(f"Error initializing plugin system: {e}")
            return False

    async def _trigger_plugin_hooks(
        self, hook_type: HookType, data: Dict[str, Any]
    ) -> List[PluginResult]:
        """Execute plugin hooks with observable error logging and failure isolation."""
        if not self.plugin_manager:
            return []
        try:
            context = PluginContext(plugin_id="", data=data)
            results = await self.plugin_manager.execute_hooks(hook_type, context)
            for r in results:
                if r and not r.success:
                    logger.warning(
                        f"Plugin hook {hook_type.value} execution reported failure: {r.error_message}",
                        hook=hook_type.value,
                        error=r.error_message,
                    )
            return results
        except Exception as e:
            logger.error(
                f"Error executing plugin hooks for {hook_type.value}: {e}",
                hook=hook_type.value,
                exc_info=True,
            )
            return []

    async def load_plugin(
        self, plugin_path: str, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Load a plugin into the system"""
        try:
            if not self.plugin_manager:
                return {"success": False, "error": "Plugin manager not initialized"}

            plugin_id = await self.plugin_manager.load_plugin(plugin_path, config)
            if plugin_id:
                return {"success": True, "plugin_id": plugin_id, "status": "loaded"}
            else:
                return {"success": False, "error": "Failed to load plugin"}
        except Exception as e:
            logger.error(f"Error loading plugin: {e}")
            return {"success": False, "error": str(e)}

    async def unload_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Unload a plugin from the system"""
        try:
            if not self.plugin_manager:
                return {"success": False, "error": "Plugin manager not initialized"}

            success = await self.plugin_manager.unload_plugin(plugin_id)
            return {
                "success": success,
                "plugin_id": plugin_id,
                "status": "unloaded" if success else "failed",
            }
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")
            return {"success": False, "error": str(e)}

    async def get_plugin_status(self, plugin_id: str) -> Dict[str, Any]:
        """Get status of a plugin"""
        try:
            if not self.plugin_manager:
                return {"success": False, "error": "Plugin manager not initialized"}

            status = await self.plugin_manager.get_plugin_status(plugin_id)
            if status:
                return {
                    "success": True,
                    "plugin_id": plugin_id,
                    "status": status.value if hasattr(status, "value") else str(status),
                }
            else:
                return {"success": False, "error": "Plugin not found"}
        except Exception as e:
            logger.error(f"Error getting plugin status: {e}")
            return {"success": False, "error": str(e)}

    async def list_plugins(self) -> Dict[str, Any]:
        """List all plugins"""
        try:
            if not self.plugin_manager:
                return {"success": False, "error": "Plugin manager not initialized"}

            plugins = await self.plugin_manager.list_plugins()
            return {"success": True, "plugins": plugins, "count": len(plugins)}
        except Exception as e:
            logger.error(f"Error listing plugins: {e}")
            return {"success": False, "error": str(e)}

    async def reload_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Reload a plugin"""
        try:
            if not self.plugin_manager:
                return {"success": False, "error": "Plugin manager not initialized"}

            result = await self.plugin_manager.reload_plugin(plugin_id)
            if result:
                return {"success": True, "plugin_id": plugin_id, "status": "reloaded"}
            else:
                return {
                    "success": False,
                    "error": f"Failed to reload plugin {plugin_id}",
                }
        except Exception as e:
            logger.error(f"Error reloading plugin {plugin_id}: {e}")
            return {"success": False, "error": str(e)}

    async def create_secure_backup(
        self, backup_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a secure backup of the vector store data.

        Args:
            backup_name: Optional name for the backup

        Returns:
            Dict containing backup result information
        """
        try:
            if not settings.vector_store.enable_secure_backup:
                return {"success": False, "error": "Secure backup is disabled"}

            logger.info("Starting secure backup creation")

            # Create backup using SecureBackupManager
            backup_result = await self.backup_manager.create_encrypted_backup(
                vector_stores=[self.vector_store],
                backup_name=backup_name,
                compression=True,
                verify_after=True,
            )

            if backup_result.status.value == "verified":
                logger.info(
                    f"Secure backup created successfully: {backup_result.backup_path}"
                )
                return {
                    "success": True,
                    "backup_id": backup_result.backup_id,
                    "backup_path": backup_result.backup_path,
                    "file_size": backup_result.file_size,
                    "compression_ratio": backup_result.compression_ratio,
                    "vector_stores_backed_up": backup_result.vector_stores_backed_up,
                }
            else:
                logger.error(f"Backup creation failed: {backup_result.errors}")
                return {
                    "success": False,
                    "error": f"Backup failed: {backup_result.errors}",
                }

        except Exception as e:
            logger.error(f"Secure backup creation failed: {e}")
            return {"success": False, "error": str(e)}

    async def restore_from_backup(self, backup_path: str) -> Dict[str, Any]:
        """
        Restore vector store data from a secure backup.

        Args:
            backup_path: Path to the backup file

        Returns:
            Dict containing restore result information
        """
        try:
            if not settings.vector_store.enable_secure_backup:
                return {"success": False, "error": "Secure backup is disabled"}

            logger.info(f"Starting restore from backup: {backup_path}")

            # Restore from backup using SecureBackupManager
            restore_result = await self.backup_manager.restore_from_backup(
                backup_path=backup_path,
                target_stores=[self.vector_store],
                verify_integrity=True,
            )

            if restore_result.status == "completed":
                logger.info(
                    f"Restore completed successfully: {restore_result.restored_documents} documents"
                )
                return {
                    "success": True,
                    "restore_id": restore_result.restore_id,
                    "restored_stores": restore_result.restored_stores,
                    "restored_documents": restore_result.restored_documents,
                    "restore_time": restore_result.restore_time,
                }
            else:
                logger.error(f"Restore failed: {restore_result.errors}")
                return {
                    "success": False,
                    "error": f"Restore failed: {restore_result.errors}",
                }

        except Exception as e:
            logger.error(f"Restore from backup failed: {e}")
            return {"success": False, "error": str(e)}

    async def rotate_encryption_keys(self) -> Dict[str, Any]:
        """
        Rotate encryption keys for enhanced security.

        Returns:
            Dict containing key rotation result information
        """
        try:
            if not settings.vector_store.enable_key_rotation:
                return {"success": False, "error": "Key rotation is disabled"}

            logger.info("Starting encryption key rotation")

            # Rotate keys using EncryptionManager
            rotation_result = await self.encryption_manager.rotate_encryption_keys()

            if rotation_result.success:
                logger.info(
                    f"Key rotation completed successfully: {rotation_result.new_key_id}"
                )
                return {
                    "success": True,
                    "old_key_id": rotation_result.old_key_id,
                    "new_key_id": rotation_result.new_key_id,
                    "documents_rotated": rotation_result.documents_rotated,
                    "rotation_time": rotation_result.rotation_time,
                }
            else:
                logger.error(f"Key rotation failed: {rotation_result.errors}")
                return {
                    "success": False,
                    "error": f"Key rotation failed: {rotation_result.errors}",
                }

        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            return {"success": False, "error": str(e)}

    def _record_metric(self, metric_name: str, value: float) -> None:
        """Record a metric value in history."""
        if metric_name in self.metrics_history:
            self.metrics_history[metric_name].append(value)
            # Keep only last 1000 values to prevent memory issues
            if len(self.metrics_history[metric_name]) > 1000:
                self.metrics_history[metric_name] = self.metrics_history[metric_name][
                    -1000:
                ]

    def _increment_counter(self, counter_name: str) -> None:
        """Increment a request counter."""
        if counter_name in self.request_counts:
            self.request_counts[counter_name] += 1

    def get_advanced_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        metrics = {
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "request_counts": dict(self.request_counts),
            "component_error_counts": dict(self.component_error_counts),
            "performance_summary": {},
            "health_status": self.get_health_status(),
        }

        # Calculate performance summaries
        for metric_name, values in self.metrics_history.items():
            if values:
                metrics["performance_summary"][metric_name] = {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 3),
                    "min": round(min(values), 3),
                    "max": round(max(values), 3),
                    "latest": round(values[-1], 3),
                }
            else:
                metrics["performance_summary"][metric_name] = {
                    "count": 0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "latest": 0.0,
                }

        # Calculate success rates
        total_queries = self.request_counts["total_queries"]
        total_ingests = self.request_counts["total_ingests"]

        metrics["success_rates"] = {
            "query_success_rate": (
                self.request_counts["successful_queries"] / total_queries
                if total_queries > 0
                else 0.0
            ),
            "ingest_success_rate": (
                self.request_counts["successful_ingests"] / total_ingests
                if total_ingests > 0
                else 0.0
            ),
        }

        return metrics

    def _initialize_default_loaders(self):
        """Initialize default loaders."""
        from ragbot.rag import PDFLoader, TextLoader, URLLoader

        try:
            from ragbot.rag import DOCXLoader  # optional

            _docx = DOCXLoader()
        except Exception:
            _docx = None

        loaders = {
            "pdf": PDFLoader(),
            "text": TextLoader(),
            "url": URLLoader(),
        }
        if _docx is not None:
            loaders["docx"] = _docx
        return loaders

    def _initialize_default_chunker(self):
        """Initialize default chunker with advanced strategy if configured."""
        try:
            strategy = getattr(settings.advanced_chunking, "chunking_strategy", "token")
        except Exception:
            strategy = "token"

        # Use AdaptiveChunker for all advanced strategies except plain token
        if strategy in ("adaptive", "semantic", "hierarchical", "full", "hybrid"):
            try:
                from ragbot.rag import AdaptiveChunker

                return AdaptiveChunker()
            except Exception:
                pass  # fallback below

        from ragbot.rag import TokenChunker

        return TokenChunker(
            chunk_size=settings.rag.chunk_size, chunk_overlap=settings.rag.chunk_overlap
        )

    def _initialize_default_embedder(self):
        """Initialize default embedder based on settings.embedding.provider."""
        try:
            provider = getattr(settings.embedding, "provider", "openai")
            if provider == "openai":
                from ragbot.rag import OpenAIEmbedder

                # Pass through settings.embedding options
                return OpenAIEmbedder(api_key=settings.openai_api_key)
            elif provider in ("sentence_transformers", "huggingface"):
                from ragbot.rag import STEmbedder

                model_name = getattr(
                    settings.embedding,
                    "model",
                    "sentence-transformers/all-MiniLM-L6-v2",
                )
                # Optional device can be read from LLM device or default auto
                device = getattr(settings.llm, "hf_device", None)
                return STEmbedder(model_name=model_name, device=device)
            else:
                # Fallback to OpenAI if unknown
                from ragbot.rag import OpenAIEmbedder

                return OpenAIEmbedder(api_key=settings.openai_api_key)
        except Exception as e:
            error_context = ErrorContext.from_exception(
                e,
                "rag_service",
                "initialize_embedder",
                provider=getattr(settings.embedding, "provider", "openai"),
                model=getattr(settings.embedding, "model", "unknown"),
            )
            logger.error(
                f"Failed to initialize default embedder: {e}",
                component="rag_service",
                operation="initialize_embedder",
                error_type=type(e).__name__,
                provider=getattr(settings.embedding, "provider", "openai"),
                model=getattr(settings.embedding, "model", "unknown"),
            )
            raise EmbeddingError(
                f"Failed to initialize embedder: {e}",
                provider=getattr(settings.embedding, "provider", "openai"),
                model=getattr(settings.embedding, "model", "unknown"),
                details=error_context.metadata,
            ) from e

    def _initialize_default_vector_store(self):
        """Initialize default vector store via provider factory aligned with settings.vector_db."""
        from ragbot.rag import VectorStoreFactory

        # Resolve provider from settings.vector_db (supports: faiss, chromadb, qdrant)
        provider = str(getattr(settings, "vector_db", "faiss")).lower()

        cfg = getattr(settings, "store", object())
        vector_store_cfg = getattr(settings, "vector_store", object())

        base_kwargs = {
            "similarity_metric": getattr(cfg, "similarity_metric", "cosine"),
            "config": vector_store_cfg,
        }

        if provider == "faiss":
            # FAISS store path and params
            store_path = getattr(cfg, "store_path", None) or str(settings.store_path)
            base_kwargs.update(
                {
                    "store_path": store_path,
                    "faiss_nlist": getattr(cfg, "faiss_nlist", 0),
                    "faiss_nprobe": getattr(cfg, "faiss_nprobe", 0),
                    "faiss_hnsw_m": getattr(cfg, "faiss_hnsw_m", 0),
                    "faiss_hnsw_ef_search": getattr(cfg, "faiss_hnsw_ef_search", 0),
                    "keep_embeddings": getattr(cfg, "store_keep_embeddings", True),
                }
            )
        elif provider in ("chroma", "chromadb"):
            default_chroma_path = str(settings.store_path / "chroma")
            base_kwargs.update(
                {
                    "persist_directory": getattr(
                        cfg, "chroma_persist_directory", default_chroma_path
                    ),
                    "collection_name": getattr(cfg, "chroma_collection_name", "ragbot"),
                    "distance_function": getattr(
                        cfg, "chroma_distance_function", "cosine"
                    ),
                }
            )
        elif provider == "qdrant":
            default_qdrant_path = str(settings.store_path / "qdrant")
            base_kwargs.update(
                {
                    "url": getattr(cfg, "qdrant_url", "http://localhost:6333"),
                    "path": getattr(cfg, "qdrant_path", default_qdrant_path),
                    "collection_name": getattr(cfg, "qdrant_collection_name", "ragbot"),
                    "vector_size": getattr(cfg, "qdrant_vector_size", 1536),
                    "timeout": getattr(cfg, "qdrant_timeout", 30),
                }
            )
        elif provider == "weaviate":
            base_kwargs.update(
                {
                    "url": getattr(cfg, "weaviate_url", "http://localhost:8080"),
                    "api_key": getattr(cfg, "weaviate_api_key", None),
                    "class_name": getattr(cfg, "weaviate_class_name", "Document"),
                    "vector_size": getattr(cfg, "weaviate_vector_size", 1536),
                    "timeout": getattr(cfg, "weaviate_timeout", 30),
                }
            )

        try:
            logger.info(
                "Initializing vector store",
                provider=provider,
                config={k: v for k, v in base_kwargs.items() if k != "url"},
            )
        except Exception:
            pass

        try:
            return VectorStoreFactory.create_store(provider, **base_kwargs)
        except Exception as e:
            logger.error(
                f"Failed to initialize vector store: {e}",
                component="rag_service",
                operation="initialize_vector_store",
                error_type=type(e).__name__,
                provider=provider,
            )
            # Fallback to FAISS on errors
            try:
                logger.warning(f"Falling back to FAISS store due to: {e}")
            except Exception:
                pass
            from ragbot.rag.store.faiss_store import FAISSStore

            return FAISSStore(store_path=str(settings.data_dir / "vector_store"))

    def _initialize_default_qa_chain(self):
        """Initialize default QA chain."""
        try:
            from ragbot.rag import QAChain

            # Get LLM provider from settings
            llm_provider = getattr(settings.llm, "provider", "openai")
            model_name = getattr(settings.llm, "model", "gpt-3.5-turbo")
            max_tokens = getattr(settings.llm, "max_tokens", None)
            temperature = getattr(settings.llm, "temperature", 0.3)
            api_key = getattr(settings, "openai_api_key", None)

            logger.info(
                f"Initializing QA chain with provider: {llm_provider}, model: {model_name}",
                provider=llm_provider,
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                has_api_key=bool(api_key),
            )

            # Initialize QAChain with correct provider and model
            qa_chain = QAChain(
                llm_provider=llm_provider,
                model_name=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                api_key=api_key,
            )

            logger.info("QA chain initialized successfully")
            return qa_chain

        except Exception as e:
            logger.error(
                f"Failed to initialize QA chain: {e}",
                component="rag_service",
                operation="initialize_qa_chain",
                error_type=type(e).__name__,
                provider=getattr(settings.llm, "provider", "openai"),
                model=getattr(settings.llm, "model", "unknown"),
                exc_info=True,
            )
            raise LLMError(
                f"Failed to initialize QA chain: {e}",
                provider=getattr(settings.llm, "provider", "openai"),
                model=getattr(settings.llm, "model", "unknown"),
                details={"error": str(e), "traceback": str(e.__traceback__)},
            ) from e

    def _initialize_document_service(self):
        """Initialize default document service."""
        return DocumentService(
            loaders=self.loaders,
            chunker=self.chunker,
            embedder=self.embedder,
            vector_store=self.vector_store,
            cache=self.cache,
        )

    async def ingest_document(
        self,
        source: str,
        source_type: str = None,
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> IngestResult:
        """
        Ingest a document into the RAG system.

        Args:
            source: Document source (file path, URL, text content)
            source_type: Type of source (pdf, url, text, etc.) - auto-detected if None
            metadata: Optional additional metadata
            tenant_id: Optional tenant identifier for multi-tenant isolation

        Returns:
            IngestResult: Result of the ingestion operation
        """
        start_time = time.time()

        self._increment_counter("total_ingests")

        # Trigger pre-ingest hook
        await self._trigger_plugin_hooks(
            HookType.PRE_DOCUMENT_INGEST,
            {
                "source": source,
                "source_type": source_type,
                "metadata": metadata,
                "tenant_id": tenant_id,
            },
        )

        # Multi-tenant limits and status verification
        if tenant_id and self.tenant_manager:
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant or (
                isinstance(tenant.status, TenantStatus)
                and tenant.status != TenantStatus.ACTIVE
            ) or (str(getattr(tenant, "status", "")).lower() != "active"):
                return IngestResult(
                    success=False,
                    document_id="",
                    chunks_created=0,
                    processing_time=0.0,
                    error_message=f"Tenant '{tenant_id}' is not active or does not exist",
                )
            can_proceed = await self.tenant_manager.check_tenant_limits(
                tenant_id, "document"
            )
            if not can_proceed:
                return IngestResult(
                    success=False,
                    document_id="",
                    chunks_created=0,
                    processing_time=0.0,
                    error_message=f"Tenant '{tenant_id}' exceeded document limits",
                )

        # Auto-detect source type if not provided
        if source_type is None:
            source_type = self._detect_source_type(source)

        document_id = f"{source_type}_{hash(source)}_{int(start_time)}"

        try:
            logger.info(f"Starting document ingestion: {source} (type: {source_type})")

            # Step 0: Validate document using DocumentService
            validation_result = await self.document_service.validate_document(
                source, source_type
            )
            if not validation_result.is_valid:
                raise DocumentProcessingError(
                    f"Document validation failed: {validation_result.errors}"
                )

            # Step 1: Load document based on type
            document = await self._load_document(source, source_type)
            logger.debug(f"Document loaded: {len(document.text)} characters")

            if not document.text.strip():
                raise DocumentProcessingError("Empty or invalid document content")

            # Step 2: Chunk document
            chunks = await self._chunk_document(document)
            logger.debug(f"Document chunked into {len(chunks)} chunks")

            # Step 3: Generate embeddings
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = await self._generate_embeddings(chunk_texts)
            logger.debug(f"Generated embeddings for {len(embeddings)} chunks")

            # Step 4: Prepare metadata for each chunk
            chunk_metadata = []
            for i, chunk in enumerate(chunks):
                span = {
                    "start": getattr(chunk, "start_index", 0),
                    "end": getattr(chunk, "end_index", 0),
                }
                chunk_meta = {
                    "chunk_id": f"{document_id}_chunk_{i}",
                    "document_id": document_id,
                    "source": source,
                    "source_type": source_type,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "span": span,
                    **({"tenant_id": tenant_id} if tenant_id else {}),
                    **chunk.metadata,
                    **(metadata or {}),
                }
                chunk_metadata.append(chunk_meta)

            # Step 5: Apply encryption if enabled
            if settings.vector_store.enable_encryption:
                try:
                    # Encrypt embeddings before storage
                    encrypted_embeddings = []
                    for embedding in embeddings:
                        (
                            encrypted_emb,
                            iv,
                            tag,
                        ) = await self.encryption_manager.encrypt_embeddings(embedding)
                        encrypted_embeddings.append(
                            {"data": encrypted_emb, "iv": iv, "tag": tag}
                        )
                    logger.debug(f"Encrypted {len(embeddings)} embeddings")
                except Exception as e:
                    logger.warning(f"Encryption failed, storing unencrypted: {e}")
                    encrypted_embeddings = None
            else:
                encrypted_embeddings = None

            # Step 6: Store in vector database
            await self._store_chunks(
                chunk_texts,
                embeddings,
                chunk_metadata,
                encrypted_embeddings,
                tenant_id=tenant_id,
            )
            logger.debug(f"Stored {len(chunks)} chunks in vector store")

            processing_time = time.time() - start_time

            result = IngestResult(
                success=True,
                document_id=document_id,
                chunks_created=len(chunks),
                processing_time=processing_time,
                metadata={
                    "source": source,
                    "source_type": source_type,
                    "content_length": len(document.text),
                    "document_metadata": document.metadata,
                    **({"tenant_id": tenant_id} if tenant_id else {}),
                },
            )

            # Track tenant usage
            if tenant_id and self.tenant_manager:
                await self.tenant_manager.track_tenant_usage(
                    tenant_id,
                    "document",
                    metadata={"chunks": len(chunks), "document_id": document_id},
                )

            # Trigger post-ingest hook
            await self._trigger_plugin_hooks(
                HookType.POST_DOCUMENT_INGEST,
                {
                    "document_id": document_id,
                    "chunks_created": len(chunks),
                    "processing_time": processing_time,
                    "tenant_id": tenant_id,
                },
            )

            logger.info(
                f"Document ingestion completed successfully: {document_id} "
                f"({len(chunks)} chunks, {processing_time:.2f}s)"
            )

            # Record metrics
            self._record_metric("ingest_duration", processing_time)
            self._increment_counter("successful_ingests")

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Error during document ingestion: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Increment error count for appropriate component
            if "load" in str(e).lower():
                self.component_error_counts["loader"] += 1
            elif "chunk" in str(e).lower():
                self.component_error_counts["chunker"] += 1
            elif "embed" in str(e).lower():
                self.component_error_counts["embedder"] += 1
            elif "store" in str(e).lower() or "vector" in str(e).lower():
                self.component_error_counts["vector_store"] += 1

            # Record failed ingest metrics
            self._record_metric("ingest_duration", processing_time)
            self._increment_counter("failed_ingests")

            return IngestResult(
                success=False,
                document_id=document_id,
                chunks_created=0,
                processing_time=processing_time,
                error_message=error_msg,
            )

    def _detect_source_type(self, source: str) -> str:
        """Auto-detect source type from content."""
        if source.startswith(("http://", "https://")):
            return "url"
        elif source.lower().endswith(".pdf") or (
            source.count("/") > 0 and ".pdf" in source.lower()
        ):
            return "pdf"
        elif source.lower().endswith(".docx"):
            return "docx"
        else:
            return "text"

    async def _load_document(self, source: str, source_type: str) -> Document:
        """Load document using appropriate loader."""
        try:
            if source_type in self.loaders:
                loader = self.loaders[source_type]
                return await loader.load(source)
            else:
                raise DocumentProcessingError(
                    f"No loader available for type: {source_type}"
                )
        except Exception as e:
            raise DocumentProcessingError(f"Failed to load document: {str(e)}") from e

    async def _chunk_document(self, document: Document) -> List[Document]:
        """Chunk document into smaller pieces."""
        try:
            return await self.chunker.chunk_document(document)
        except Exception as e:
            raise DocumentProcessingError(f"Failed to chunk document: {str(e)}") from e

    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text chunks."""
        if not self.embedder:
            logger.error("Embedder is not available")
            raise EmbeddingError(
                "Embedder is not available",
                provider="unknown",
                model="unknown",
                details={"error": "Embedder not initialized"},
            )

        try:
            timeout = 60.0  # Default timeout
            started = time.time()
            res = await asyncio.wait_for(
                self.embedder.embed_texts(texts), timeout=timeout
            )
            try:
                logger.info(
                    "Embeddings generated",
                    count=len(res),
                    duration=f"{time.time() - started:.2f}s",
                    timeout_sec=timeout,
                )
            except Exception:
                pass

            # Record embedding duration metric
            duration = time.time() - started
            self._record_metric("embedding_duration", duration)

            return res
        except Exception as e:
            raise EmbeddingError(f"Failed to generate embeddings: {str(e)}") from e

    async def _store_chunks(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadata: List[Dict[str, Any]],
        encrypted_embeddings: Optional[List[Dict[str, Any]]] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        """Store chunks in vector store with optional encryption and tenant isolation."""
        try:
            timeout = 60.0  # Default timeout
            started = time.time()

            # Store encrypted embeddings in metadata if available
            if encrypted_embeddings:
                for i, meta in enumerate(metadata):
                    if i < len(encrypted_embeddings):
                        meta["_encrypted_embedding"] = encrypted_embeddings[i]
                        meta["_encryption_enabled"] = True

            target_store = self.get_vector_store(tenant_id)
            if not target_store:
                raise DocumentProcessingError("Target vector store is not available")

            await asyncio.wait_for(
                target_store.add_texts(texts, embeddings, metadata),
                timeout=timeout,
            )
            try:
                logger.info(
                    "Vector add completed",
                    items=len(texts),
                    duration=f"{time.time() - started:.2f}s",
                    timeout_sec=timeout,
                    tenant_id=tenant_id,
                )
            except Exception:
                pass
        except Exception as e:
            raise DocumentProcessingError(f"Failed to store chunks: {str(e)}") from e

    async def query_documents(
        self,
        question: str,
        lang: str = "en",
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        tenant_id: Optional[str] = None,
    ) -> QueryResult:
        """
        Query documents and generate an answer.

        Args:
            question: User question
            lang: Response language (en, fa)
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity threshold
            tenant_id: Optional tenant identifier for isolation

        Returns:
            QueryResult: Query result with answer and sources
        """
        start_time = time.time()
        self.last_query_time = datetime.now()

        self._increment_counter("total_queries")

        # Trigger pre-query hook
        await self._trigger_plugin_hooks(
            HookType.PRE_QUERY,
            {
                "question": question,
                "lang": lang,
                "top_k": top_k,
                "tenant_id": tenant_id,
            },
        )

        # Multi-tenant status and limits check
        if tenant_id and self.tenant_manager:
            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant or (
                isinstance(tenant.status, TenantStatus)
                and tenant.status != TenantStatus.ACTIVE
            ) or (str(getattr(tenant, "status", "")).lower() != "active"):
                return QueryResult(
                    answer=f"Tenant '{tenant_id}' is not active or does not exist",
                    sources=[],
                    confidence_score=0.0,
                    processing_time=0.0,
                    language=lang,
                    metadata={"error": "tenant_inactive_or_not_found", "tenant_id": tenant_id},
                )
            can_proceed = await self.tenant_manager.check_tenant_limits(
                tenant_id, "query"
            )
            if not can_proceed:
                return QueryResult(
                    answer=f"Tenant '{tenant_id}' exceeded daily query limits",
                    sources=[],
                    confidence_score=0.0,
                    processing_time=0.0,
                    language=lang,
                    metadata={"error": "tenant_limit_exceeded", "tenant_id": tenant_id},
                )

        # trace id for this request
        trace_id = f"q-{int(time.time() * 1000)}"
        # enforce question length limit
        try:
            max_q = int(
                getattr(getattr(settings, "rag", object()), "max_question_chars", 2000)
            )
            if len(question) > max_q:
                question = question[:max_q]
        except Exception:
            pass
        logger.info(
            f"Processing query: {question[:100]}... (lang: {lang})", trace_id=trace_id
        )

        # Use settings defaults if not provided
        top_k = top_k or settings.rag.top_k

        # Check semantic cache first
        if self.semantic_cache:
            try:
                cached_result = await self.semantic_cache.get_similar_answer(
                    question, tenant_id=tenant_id
                )
                if cached_result:
                    logger.info("Found semantically similar answer in cache")
                    cached_qr = QueryResult(
                        answer=cached_result.answer,
                        sources=cached_result.context,
                        confidence_score=cached_result.confidence_score,
                        processing_time=time.time() - start_time,
                        language=lang,
                        retrieved_chunks=cached_result.context,
                        metadata={
                            **cached_result.metadata,
                            "cached": True,
                            **({"tenant_id": tenant_id} if tenant_id else {}),
                        },
                    )
                    await self._trigger_plugin_hooks(
                        HookType.PRE_RESPONSE,
                        {
                            "question": question,
                            "answer": cached_qr.answer,
                            "cached": True,
                            "tenant_id": tenant_id,
                        },
                    )
                    await self._trigger_plugin_hooks(
                        HookType.POST_RESPONSE,
                        {"result": cached_qr, "tenant_id": tenant_id},
                    )
                    return cached_qr
            except Exception as e:
                logger.warning(f"Error checking semantic cache: {e}")
                self.component_error_counts["semantic_cache"] += 1

        try:
            # Step 1: Use Advanced Retriever if available
            retriever = self.get_retriever(tenant_id)
            if retriever:
                logger.debug("Using retriever for search")
                retrieved_chunks = await retriever.retrieve(
                    question, top_k=top_k
                )
                logger.debug(
                    f"Retriever found {len(retrieved_chunks)} relevant chunks"
                )
            else:
                # Fallback to basic retrieval
                logger.debug("Using basic retriever")
                question_embedding = await self._embed_question(question)
                search_result = await self._retrieve_context(
                    question_embedding, top_k, similarity_threshold, tenant_id=tenant_id
                )
                retrieved_chunks = (
                    search_result.documents
                    if hasattr(search_result, "documents")
                    else []
                )
                logger.debug(
                    f"Basic retriever found {len(retrieved_chunks)} relevant chunks"
                )

            # Trigger post-query hook
            await self._trigger_plugin_hooks(
                HookType.POST_QUERY,
                {
                    "question": question,
                    "retrieved_count": len(retrieved_chunks),
                    "tenant_id": tenant_id,
                },
            )

            # Step 1.5: Apply advanced query features if enabled
            if retrieved_chunks and settings.vector_store.enable_advanced_queries:
                try:
                    # Apply query optimization
                    if settings.vector_store.enable_query_optimization:
                        optimization_result = await self.query_optimizer.optimize_query(
                            question, context={"retrieved_docs": len(retrieved_chunks)}
                        )
                        logger.debug(
                            f"Query optimization: {optimization_result.improvement_percentage:.2f}% improvement"
                        )

                    # Apply custom scoring
                    if settings.vector_store.enable_custom_scoring:
                        scored_chunks = await self.custom_scorer.hybrid_scoring(
                            retrieved_chunks,
                            strategy_weights={
                                "semantic": 0.6,
                                "time_decay": 0.2,
                                "popularity": 0.2,
                            },
                        )
                        # Convert ScoredDocument back to VectorDocument
                        retrieved_chunks = [
                            VectorDocument(
                                id=scored_doc.document_id,
                                content=scored_doc.content,
                                embedding=[],  # Will be filled by vector store
                                metadata=scored_doc.metadata,
                                score=scored_doc.final_score,
                            )
                            for scored_doc in scored_chunks
                        ]
                        logger.debug(
                            f"Applied custom scoring to {len(retrieved_chunks)} chunks"
                        )

                    # Apply advanced filtering if needed
                    if settings.vector_store.enable_aggregation:
                        # Example: Filter by date range if question contains time references
                        if any(
                            word in question.lower()
                            for word in [
                                "recent",
                                "latest",
                                "new",
                                "old",
                                "today",
                                "yesterday",
                            ]
                        ):
                            try:
                                from datetime import timedelta

                                recent_docs = (
                                    await self.advanced_filter.date_range_filter(
                                        field="created_at",
                                        start_date=(
                                            datetime.now() - timedelta(days=30)
                                        ).strftime("%Y-%m-%d"),
                                        end_date=datetime.now().strftime("%Y-%m-%d"),
                                    )
                                )
                                if recent_docs:
                                    # Filter retrieved chunks by recent document IDs
                                    retrieved_chunks = [
                                        doc
                                        for doc in retrieved_chunks
                                        if doc.id in recent_docs
                                    ]
                                    logger.debug(
                                        f"Applied date filter, {len(retrieved_chunks)} recent chunks"
                                    )
                            except Exception as e:
                                logger.warning(f"Date filtering failed: {e}")

                except Exception as e:
                    logger.warning(f"Advanced query features failed: {e}")
                    # Continue with original chunks if advanced features fail

            # Step 3: Prepare and clamp context by token budget if configured
            context_texts = (
                [chunk.content for chunk in retrieved_chunks]
                if retrieved_chunks
                else []
            )
            try:
                max_ctx_tokens = int(
                    getattr(
                        getattr(settings, "rag", object()), "max_context_tokens", 4000
                    )
                )
            except Exception:
                max_ctx_tokens = 0
            if max_ctx_tokens > 0 and context_texts:
                try:
                    import tiktoken as _tk  # type: ignore

                    enc = None
                    try:
                        enc = _tk.get_encoding("cl100k_base")
                    except Exception:
                        names = _tk.list_encoding_names()
                        enc = _tk.get_encoding(names[0]) if names else None
                    budget = max_ctx_tokens
                    trimmed: List[str] = []
                    total = 0
                    for t in context_texts:
                        if not enc:
                            toks = len(t.split())
                        else:
                            toks = len(enc.encode(t))
                        if total + toks > budget:
                            # keep partial if it helps
                            remain = budget - total
                            if remain > 10:
                                words = t.split()
                                trimmed.append(" ".join(words[:remain]))
                                total = budget
                            break
                        trimmed.append(t)
                        total += toks
                    if trimmed:
                        context_texts = trimmed
                        logger.info(
                            "Context trimmed to token budget",
                            trace_id=trace_id,
                            tokens=total,
                            budget=budget,
                        )
                except Exception:
                    pass

            # Step 4: Generate answer
            answer_text = await self._generate_answer(context_texts, question, lang)
            logger.debug(f"Generated answer: {len(answer_text)} characters")

            # Trigger pre-response hook
            await self._trigger_plugin_hooks(
                HookType.PRE_RESPONSE,
                {
                    "question": question,
                    "answer": answer_text,
                    "tenant_id": tenant_id,
                },
            )

            processing_time = time.time() - start_time

            # Record performance metrics
            if self.performance_monitor:
                try:
                    await self.performance_monitor.record_request(
                        processing_time, success=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to record performance metrics: {e}")

            # Extract sources
            sources = []
            if retrieved_chunks:
                for chunk in retrieved_chunks:
                    source = chunk.metadata.get("source")
                    if source and source not in sources:
                        sources.append(source)

            # Calculate confidence score based on number of relevant chunks found
            confidence_score = (
                min(1.0, len(retrieved_chunks) / top_k) if retrieved_chunks else 0.0
            )

            # Build citations/grounding metadata from retrieved chunks
            citations: List[Dict[str, Any]] = []
            try:
                if retrieved_chunks:
                    for ch in retrieved_chunks[: top_k or len(retrieved_chunks)]:
                        meta = getattr(ch, "metadata", {}) or {}
                        citations.append(
                            {
                                "source": meta.get("source")
                                or meta.get("source_path")
                                or meta.get("file_name"),
                                "page": meta.get("page"),
                                "slide": meta.get("slide"),
                                "span": {
                                    "start": getattr(ch, "start_index", None)
                                    or meta.get("start_index"),
                                    "end": getattr(ch, "end_index", None)
                                    or meta.get("end_index"),
                                },
                                "score": getattr(ch, "score", None),
                                "chunk_id": meta.get("chunk_id"),
                                "document_id": meta.get("document_id"),
                                "structure": meta.get("structure_type")
                                or meta.get("chunk_type"),
                                "heading_level": meta.get("level"),
                            }
                        )
            except Exception:
                citations = []

            # Build human-friendly references from citations
            references: List[str] = []
            try:
                for c in citations:
                    src = c.get("source") or "unknown"
                    pg = c.get("page")
                    sl = c.get("slide")
                    if pg:
                        ref = f"{src} (page {pg})"
                    elif sl:
                        ref = f"{src} (slide {sl})"
                    else:
                        ref = str(src)
                    if ref not in references:
                        references.append(ref)
            except Exception:
                references = []

            result = QueryResult(
                answer=answer_text,
                sources=sources,
                confidence_score=confidence_score,
                processing_time=processing_time,
                language=lang,
                retrieved_chunks=[
                    chunk.content[:100] + "..." for chunk in retrieved_chunks[:3]
                ]
                if retrieved_chunks
                else [],
                metadata={
                    "question": question,
                    "retrieved_count": len(retrieved_chunks),
                    "top_k": top_k,
                    "similarity_threshold": similarity_threshold,
                    "citations": citations,
                    "references": references,
                    **({"tenant_id": tenant_id} if tenant_id else {}),
                },
            )

            # Cache the result in semantic cache if confidence is high enough
            if self.semantic_cache and confidence_score > 0.7:
                try:
                    await self.semantic_cache.cache_answer(
                        query=question,
                        answer=answer_text,
                        context=context_texts,
                        metadata={
                            "language": lang,
                            "timestamp": time.time(),
                            "top_k": top_k,
                            "similarity_threshold": similarity_threshold,
                            "retrieved_count": len(retrieved_chunks),
                        },
                        confidence_score=confidence_score,
                        tenant_id=tenant_id,
                    )
                    logger.debug("Answer cached in semantic cache")
                except Exception as e:
                    logger.warning(f"Failed to cache answer: {e}")
                    self.component_error_counts["semantic_cache"] += 1

            # Track tenant usage
            if tenant_id and self.tenant_manager:
                await self.tenant_manager.track_tenant_usage(
                    tenant_id,
                    "query",
                    metadata={
                        "question": question[:100],
                        "confidence": confidence_score,
                    },
                )

            # Trigger post-response hook
            await self._trigger_plugin_hooks(
                HookType.POST_RESPONSE,
                {"result": result, "tenant_id": tenant_id},
            )

            logger.info(
                f"Query processed successfully: {len(answer_text)} chars answer, "
                f"{len(sources)} sources, {processing_time:.2f}s"
            )

            # Record successful query metrics
            self._record_metric("query_duration", processing_time)
            self._increment_counter("successful_queries")

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Error processing query: {str(e)}"

            # Record performance metrics for failed request
            if self.performance_monitor:
                try:
                    await self.performance_monitor.record_request(
                        processing_time, success=False
                    )
                except Exception as perf_e:
                    logger.warning(f"Failed to record performance metrics: {perf_e}")

            # Check if it's a pydantic-related error
            if "pydantic" in str(e).lower() or "__pydantic" in str(e):
                log_pydantic_error(
                    e,
                    context="rag_service_query_documents",
                    question=question[:100],
                    language=lang,
                    processing_time=processing_time,
                )
            else:
                logger.error_with_traceback(
                    error_msg,
                    exc_info=True,
                    question=question[:100],
                    language=lang,
                    processing_time=processing_time,
                    error_type=type(e).__name__,
                    error_details=str(e),
                )

            # Increment error count for appropriate component
            if "embed" in str(e).lower():
                self.component_error_counts["embedder"] += 1
            elif "retrieve" in str(e).lower() or "vector" in str(e).lower():
                self.component_error_counts["vector_store"] += 1
            elif "answer" in str(e).lower() or "generate" in str(e).lower():
                self.component_error_counts["qa_chain"] += 1

            # Record failed query metrics
            self._record_metric("query_duration", processing_time)
            self._increment_counter("failed_queries")

            # Return fallback response
            return await self._create_fallback_response(
                question, lang, start_time, "processing_failed"
            )

    async def process_query(self, question: str, **kwargs: Any) -> Dict[str, Any]:
        """Convenience wrapper around query returning dict matching API/test expectations."""
        res = await self.query(question, **kwargs)
        if isinstance(res, QueryResult):
            return {
                "answer": res.answer,
                "sources": res.sources,
                "confidence": getattr(res, "confidence_score", 1.0),
                "metadata": getattr(res, "metadata", {}),
            }
        elif isinstance(res, dict):
            return res
        return {
            "answer": getattr(res, "answer", str(res)),
            "sources": getattr(res, "sources", []),
            "confidence": getattr(res, "confidence_score", 1.0),
        }

    async def process_query_with_metadata(
        self, query: str, metadata_filter: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Convenience wrapper for query with metadata filtering."""
        return await self.process_query(query, **kwargs)

    async def _embed_question(self, question: str) -> List[float]:
        """Embed a question using the embedding service."""
        if not self.embedder:
            logger.error("Embedder is not available")
            raise EmbeddingError(
                "Embedder is not available",
                provider="unknown",
                model="unknown",
                details={"error": "Embedder not initialized"},
            )

        logger.info(f"Embedding question: {question[:100]}...")
        embeddings = await self.embedder.embed_texts([question])
        logger.info(f"Generated embedding with dimension: {len(embeddings[0])}")
        return embeddings[0]

    async def _retrieve_context(
        self,
        qvec: List[float],
        top_k: int,
        similarity_threshold: Optional[float] = None,
        tenant_id: Optional[str] = None,
    ):
        """Retrieve context chunks from vector store with tenant isolation."""
        target_store = self.get_vector_store(tenant_id)
        if not target_store:
            logger.error("Vector store is not available")
            raise DocumentProcessingError("Vector store is not available")

        logger.info(
            "Searching vector store for context",
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            embedding_dimension=len(qvec),
            tenant_id=tenant_id,
        )

        timeout = 30.0  # Default timeout
        started = time.time()
        # Retry with backoff on transient errors
        max_retries = int(
            getattr(getattr(settings, "rag", object()), "vector_search_retries", 2)
        )
        backoff_base = float(
            getattr(
                getattr(settings, "rag", object()), "vector_search_backoff_base", 0.5
            )
        )
        attempt = 0
        last_err: Optional[Exception] = None
        results = None
        while attempt <= max_retries:
            try:
                results = await asyncio.wait_for(
                    target_store.search(qvec, top_k=top_k), timeout=timeout
                )
                break
            except Exception as e:
                last_err = e
                if attempt == max_retries:
                    raise
                # exponential backoff
                delay = backoff_base * (2**attempt)
                try:
                    logger.warning(
                        "Vector search failed, retrying",
                        attempt=attempt + 1,
                        retries=max_retries + 1,
                        delay_s=round(delay, 2),
                        error=str(e),
                    )
                except Exception:
                    pass
                await asyncio.sleep(delay)
                attempt += 1
        if results is None and last_err is not None:
            raise last_err
        try:
            logger.info(
                "Vector search completed",
                top_k=top_k,
                duration=f"{time.time() - started:.2f}s",
                timeout_sec=timeout,
            )
        except Exception:
            pass

        # Record retrieval duration metric
        duration = time.time() - started
        self._record_metric("retrieval_duration", duration)

        # Filter by similarity threshold if provided
        if similarity_threshold is not None and hasattr(results, "documents"):
            pre_count = len(results.documents)
            filtered_docs = [
                doc
                for doc in results.documents
                if doc.score and doc.score >= similarity_threshold
            ]
            results.documents = filtered_docs
            logger.info(
                "Filtered documents by similarity threshold",
                original_count=pre_count,
                filtered_count=len(filtered_docs),
                threshold=similarity_threshold,
            )

        # Apply decryption if enabled and documents have encrypted embeddings
        if (
            hasattr(results, "documents")
            and results.documents
            and settings.vector_store.enable_encryption
        ):
            try:
                docs = results.documents
                decrypted_docs = []
                for doc in docs:
                    meta = getattr(doc, "metadata", {}) or {}
                    if (
                        meta.get("_encryption_enabled")
                        and "_encrypted_embedding" in meta
                    ):
                        try:
                            # Decrypt the embedding
                            encrypted_data = meta["_encrypted_embedding"]
                            decrypted_embedding = (
                                await self.encryption_manager.decrypt_embeddings(
                                    encrypted_data["data"],
                                    iv=encrypted_data.get("iv"),
                                    tag=encrypted_data.get("tag"),
                                )
                            )
                            # Update document with decrypted embedding
                            doc.embedding = decrypted_embedding
                            logger.debug(f"Decrypted embedding for document {doc.id}")
                        except Exception as e:
                            logger.warning(
                                f"Failed to decrypt embedding for document {doc.id}: {e}"
                            )
                    decrypted_docs.append(doc)
                results.documents = decrypted_docs
            except Exception as e:
                logger.warning(f"Decryption process failed: {e}")

        # Apply simple parent-child boost if hierarchical metadata exists
        if hasattr(results, "documents") and results.documents:
            try:
                docs = results.documents
                # Build parent score map
                parent_scores: Dict[str, float] = {}
                for d in docs:
                    meta = getattr(d, "metadata", {}) or {}
                    parent_id = meta.get("parent_id")
                    if parent_id:
                        parent_scores[parent_id] = max(
                            parent_scores.get(parent_id, 0.0),
                            getattr(d, "score", 0.0) or 0.0,
                        )
                # Boost children by parent score fraction
                boosted: List[Any] = []
                for d in docs:
                    meta = getattr(d, "metadata", {}) or {}
                    pid = meta.get("parent_id")
                    score = getattr(d, "score", 0.0) or 0.0
                    if pid and pid in parent_scores:
                        score = min(1.0, score + 0.1 * parent_scores[pid])
                    # Recreate SearchResult item preserving structure
                    d.score = score  # type: ignore[attr-defined]
                    boosted.append(d)
                results.documents = sorted(
                    boosted, key=lambda x: getattr(x, "score", 0.0), reverse=True
                )
            except Exception as e:
                logger.debug(f"Parent-child boost skipped: {e}")

        # Log detailed information about retrieved documents
        if hasattr(results, "documents") and results.documents:
            doc_summaries = []
            for i, doc in enumerate(results.documents):
                doc_info = {
                    "rank": i + 1,
                    "doc_id": getattr(doc, "id", "unknown"),
                    "content_preview": doc.content[:100] + "..."
                    if len(doc.content) > 100
                    else doc.content,
                    "content_length": len(doc.content),
                    "score": getattr(doc, "score", "N/A"),
                    "metadata": getattr(doc, "metadata", {}),
                }
                doc_summaries.append(doc_info)

            logger.info(
                "Retrieved documents from vector store:",
                documents=doc_summaries,
                total_context_length=sum(len(doc.content) for doc in results.documents),
            )

            # Log detailed document information
            logger.info("📄 Retrieved documents content:")
            for i, doc in enumerate(results.documents):
                logger.info(f"  📄 Document {i + 1}:")
                logger.info(f"    ID: {getattr(doc, 'id', 'unknown')}")
                logger.info(
                    f"    Content: {doc.content[:300]}{'...' if len(doc.content) > 300 else ''}"
                )
                logger.info(f"    Length: {len(doc.content)} chars")
                logger.info(f"    Score: {getattr(doc, 'score', 'unknown')}")
                logger.info(f"    Metadata: {getattr(doc, 'metadata', {})}")
                logger.info("")
        else:
            logger.warning(
                "No documents found in vector store search",
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )

        return results

    async def _generate_answer(
        self, context: List[str], question: str, lang: str
    ) -> str:
        """Generate answer using the QA chain."""
        logger.info(
            "Generating answer using QA chain",
            question_length=len(question),
            context_count=len(context),
            context_total_length=sum(len(c) for c in context),
            language=lang,
            question_preview=question[:100] + "..."
            if len(question) > 100
            else question,
        )

        # Log context details
        if context:
            logger.info("🤖 Context sent to AI:")
            for i, ctx in enumerate(context):
                logger.info(f"  📝 Context {i + 1}:")
                logger.info(f"    Length: {len(ctx)} chars")
                logger.info(
                    f"    Content: {ctx[:500]}{'...' if len(ctx) > 500 else ''}"
                )
                logger.info("")

            context_summaries = []
            for i, ctx in enumerate(context):
                context_info = {
                    "index": i + 1,
                    "length": len(ctx),
                    "preview": ctx[:100] + "..." if len(ctx) > 100 else ctx,
                }
                context_summaries.append(context_info)

            logger.info(
                "Context details for answer generation:",
                contexts=context_summaries,
            )
        else:
            logger.warning(
                "No context provided for answer generation",
                question=question[:100],
                language=lang,
            )

        qa_start_time = time.time()

        # Check if QA chain is available
        if not self.qa_chain:
            logger.error("QA chain is not available")
            raise LLMError(
                "QA chain is not available",
                provider="unknown",
                model="unknown",
                details={"error": "QA chain not initialized"},
            )

        # Convert context strings to VectorDocument objects
        context_docs = []
        for i, ctx_text in enumerate(context):
            context_docs.append(
                VectorDocument(
                    id=f"context_{i}",
                    content=ctx_text,
                    embedding=[],
                    metadata={"source": "query_context", "index": i},
                )
            )

        logger.info(f"Calling QA chain with {len(context_docs)} context documents")

        answer = await self.qa_chain.answer(
            question, language=lang, context_docs=context_docs
        )
        answer_text = (
            answer.get("answer", "") if isinstance(answer, dict) else str(answer)
        )

        # Record QA duration metric
        qa_duration = time.time() - qa_start_time
        self._record_metric("qa_duration", qa_duration)

        # Optional metrics hook
        try:
            if self.performance_monitor:
                await self.performance_monitor.record_generation(
                    question_length=len(question),
                    context_count=len(context),
                    language=lang,
                )
        except Exception:
            pass

        logger.info(
            "Answer generated successfully",
            answer_length=len(answer_text),
            answer_preview=answer_text[:200] + "..."
            if len(answer_text) > 200
            else answer_text,
            language=lang,
        )

        return answer_text

    async def _create_fallback_response(
        self, question: str, lang: str, start_time: float, failure_reason: str
    ) -> QueryResult:
        """Create a fallback response when services fail."""
        processing_time = time.time() - start_time

        # Get fallback message based on language
        if lang == "fa":
            fallback_messages = {
                "embedding_failed": "متأسفانه در حال حاضر امکان پردازش سوال شما وجود ندارد. لطفاً بعداً دوباره تلاش کنید.",
                "generation_failed": "متأسفانه در تولید پاسخ مشکلی پیش آمده است. لطفاً سوال خود را ساده‌تر بیان کنید.",
                "general": "متأسفانه سیستم در حال حاضر با مشکل فنی مواجه است. لطفاً چند دقیقه دیگر دوباره تلاش کنید.",
            }
        else:
            fallback_messages = {
                "embedding_failed": "I'm currently unable to process your question. Please try again later.",
                "generation_failed": "I encountered an issue generating a response. Please try rephrasing your question.",
                "general": "The system is currently experiencing technical difficulties. Please try again in a few minutes.",
            }

        fallback_answer = fallback_messages.get(
            failure_reason, fallback_messages["general"]
        )

        return QueryResult(
            answer=fallback_answer,
            sources=[],
            confidence_score=0.0,
            processing_time=processing_time,
            language=lang,
            retrieved_chunks=[],
            metadata={
                "question": question,
                "retrieved_count": 0,
                "degraded": True,
                "failure_reason": failure_reason,
                "fallback": True,
            },
        )

    async def reset_store(self, tenant_id: Optional[str] = None) -> bool:
        """
        Reset the vector store and clear associated caches (global or tenant-specific).

        Args:
            tenant_id: Optional tenant ID to isolate reset to a single tenant.

        Returns:
            bool: True if reset was successful, False otherwise
        """
        try:
            if tenant_id:
                logger.info(f"Resetting vector store and cache for tenant: {tenant_id}")
                store = self.get_vector_store(tenant_id)
                if hasattr(store, "clear"):
                    maybe = store.clear()
                    if hasattr(maybe, "__await__"):
                        await maybe
                elif hasattr(store, "reset"):
                    maybe = store.reset()
                    if hasattr(maybe, "__await__"):
                        await maybe
                else:
                    cfg = getattr(settings, "store", object())
                    base_store_path = settings.store_path
                    tenant_path = base_store_path / "tenants" / tenant_id
                    if tenant_path.exists():
                        shutil.rmtree(tenant_path, ignore_errors=True)

                self._tenant_vector_stores.pop(tenant_id, None)
                self._tenant_retrievers.pop(tenant_id, None)

                if self.semantic_cache is not None:
                    try:
                        await self.semantic_cache.clear_cache(tenant_id=tenant_id)
                    except Exception as cache_err:
                        logger.warning(
                            f"Failed to clear semantic cache for tenant {tenant_id}: {cache_err}"
                        )

                return True

            logger.info("Resetting default vector store and associated caches")

            # 1. Reset vector store
            if hasattr(self.vector_store, "clear"):
                maybe = self.vector_store.clear()
                if hasattr(maybe, "__await__"):
                    await maybe
            elif hasattr(self.vector_store, "reset"):
                maybe = self.vector_store.reset()
                if hasattr(maybe, "__await__"):
                    await maybe
            else:
                store_path = settings.data_dir / "vector_store"
                if store_path.exists():
                    shutil.rmtree(store_path, ignore_errors=True)
                store_path.mkdir(parents=True, exist_ok=True)
                self.vector_store = self._initialize_default_vector_store()

            self._tenant_vector_stores.clear()
            self._tenant_retrievers.clear()

            # 2. Clear semantic cache if present
            if self.semantic_cache is not None:
                try:
                    if hasattr(self.semantic_cache, "clear_cache"):
                        await self.semantic_cache.clear_cache()
                    elif hasattr(self.semantic_cache, "clear"):
                        maybe_sc = self.semantic_cache.clear()
                        if hasattr(maybe_sc, "__await__"):
                            await maybe_sc
                    elif hasattr(self.semantic_cache, "cache") and hasattr(
                        self.semantic_cache.cache, "clear"
                    ):
                        self.semantic_cache.cache.clear()
                except Exception as cache_err:
                    logger.warning(
                        f"Failed to clear semantic cache during reset: {cache_err}"
                    )

            # 3. Clear general cache manager if present
            if self.cache is not None:
                try:
                    if hasattr(self.cache, "clear"):
                        maybe_c = self.cache.clear()
                        if hasattr(maybe_c, "__await__"):
                            await maybe_c
                except Exception as cache_err:
                    logger.warning(
                        f"Failed to clear general cache during reset: {cache_err}"
                    )

            # Reset error counts
            self.component_error_counts = {
                key: 0 for key in self.component_error_counts
            }

            logger.info("Vector store and associated caches reset successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to reset vector store: {str(e)}", exc_info=True)
            return False

    async def get_health_status(self) -> HealthStatus:
        """
        Get comprehensive health status of all components.

        Returns:
            HealthStatus: Current health status of the system
        """
        current_time = datetime.now()
        uptime = (current_time - self.start_time).total_seconds()

        # Check each component
        components = {}

        # Check individual components
        for component_name in [
            "loader",
            "chunker",
            "embedder",
            "vector_store",
            "retriever",
            "qa_chain",
        ]:
            error_count = self.component_error_counts[component_name]

            if error_count == 0:
                status = "healthy"
            elif error_count < 5:
                status = "degraded"
            else:
                status = "unhealthy"

            components[component_name] = ComponentHealth(
                status=status,
                last_check=current_time,
                error_count=error_count,
                details={"component_type": component_name},
            )

        # Perform actual health checks on components if available
        try:
            if hasattr(self.vector_store, "health_check"):
                await self.vector_store.health_check()
                components["vector_store"].details["connectivity"] = "ok"
        except Exception as e:
            components["vector_store"].status = "unhealthy"
            components["vector_store"].details["error"] = str(e)

        # Determine overall status
        statuses = [comp.status for comp in components.values()]
        if all(status == "healthy" for status in statuses):
            overall_status = "healthy"
        elif any(status == "unhealthy" for status in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        # Get document count
        try:
            document_count = (
                await self.vector_store.get_count()
                if hasattr(self.vector_store, "get_count")
                else 0
            )
        except Exception:
            document_count = -1

        return HealthStatus(
            overall_status=overall_status,
            components=components,
            timestamp=current_time,
            uptime=uptime,
            document_count=document_count,
            last_query_time=self.last_query_time,
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the RAG service.

        Returns:
            Dict[str, Any]: Health status information
        """
        try:
            # Get comprehensive health status
            health_status = await self.get_health_status()

            # Test basic functionality
            test_query = "What is the capital of France?"

            # Test document count
            doc_count = await self.get_document_count()

            return {
                "status": health_status.overall_status,
                "service_name": "RAGService",
                "uptime_seconds": health_status.uptime,
                "document_count": health_status.document_count,
                "last_query_time": health_status.last_query_time.isoformat()
                if health_status.last_query_time
                else None,
                "components_status": {
                    name: {
                        "status": comp.status,
                        "error_count": comp.error_count,
                        "last_check": comp.last_check.isoformat()
                        if comp.last_check
                        else None,
                    }
                    for name, comp in health_status.components.items()
                },
                "test_query_available": bool(test_query),
                "test_document_count": doc_count,
                "last_check": time.time(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "service_name": "RAGService",
                "error": str(e),
                "last_check": time.time(),
            }

    async def add_document(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> IngestResult:
        """Add a text document to the system. Convenience method for direct text ingestion."""
        return await self.ingest_document(content, "text", metadata)

    async def get_document_count(self) -> int:
        """Get the number of documents in the vector store."""
        try:
            return (
                await self.vector_store.get_count()
                if hasattr(self.vector_store, "get_count")
                else 0
            )
        except Exception:
            return 0

    async def batch_ingest(
        self,
        sources: Optional[List[str]] = None,
        *,
        directory: Optional[str] = None,
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
        source_type: Optional[str] = None,
        max_concurrency: int = 4,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Batch-ingest multiple sources with optional directory scan.

        Args:
            sources: Explicit list of sources (files, URLs, or raw text)
            directory: If provided, scan this directory for files to ingest
            patterns: Glob patterns for directory scan (e.g., ["*.pdf", "*.txt"])
            recursive: Whether to scan subdirectories
            source_type: Force source type (pdf|url|text); auto-detect if None
            max_concurrency: Max concurrent ingests
            metadata: Optional metadata applied to all items

        Returns:
            Summary dict with per-item results
        """
        from pathlib import Path

        started = time.time()

        # Collect candidate sources
        items: List[str] = []
        if sources:
            items.extend([s for s in sources if s])

        if directory:
            base = Path(directory)
            if base.exists():
                # Default to PDF only; caller/CLI can include txt/docx via patterns
                pats = patterns or ["*.pdf"]
                for pat in pats:
                    if recursive:
                        items.extend([str(p) for p in base.rglob(pat)])
                    else:
                        items.extend([str(p) for p in base.glob(pat)])
            else:
                logger.warning(f"Batch ingest directory not found: {directory}")

        # De-duplicate
        seen = set()
        unique_items = []
        for it in items:
            if it not in seen:
                seen.add(it)
                unique_items.append(it)

        if not unique_items:
            return {
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "duration": 0.0,
                "results": [],
            }

        sem = asyncio.Semaphore(max_concurrency)
        results: List[IngestResult] = []

        async def _ingest_one(src: str) -> None:
            async with sem:
                try:
                    st = source_type or self._detect_source_type(src)
                    res = await self.ingest_document(src, st, metadata)
                    results.append(res)
                except Exception as e:  # Safety net
                    results.append(
                        IngestResult(
                            success=False,
                            document_id=f"batch_{hash(src)}",
                            chunks_created=0,
                            processing_time=0.0,
                            error_message=str(e),
                            metadata={
                                "source": src,
                                "source_type": source_type or "auto",
                            },
                        )
                    )

        await asyncio.gather(*[_ingest_one(src) for src in unique_items])

        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded
        duration = time.time() - started

        logger.info(
            "Batch ingest completed",
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            duration=f"{duration:.2f}s",
        )

        # Summarize
        summary = {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "duration": duration,
            "results": [
                {
                    "success": r.success,
                    "document_id": r.document_id,
                    "chunks_created": r.chunks_created,
                    "processing_time": r.processing_time,
                    "error": r.error_message,
                    **(r.metadata or {}),
                }
                for r in results
            ],
        }
        return summary

    def _initialize_advanced_retriever(self):
        """Initialize advanced retriever with settings."""
        try:
            from ragbot.rag import AdvancedRetriever

            # Get settings
            adv_settings = settings.advanced_retrieval

            # Initialize advanced retriever with all new settings
            advanced_retriever = AdvancedRetriever(
                vector_store=self.vector_store,
                embedder=self.embedder,
                # Core settings
                enable_reranking=adv_settings.enable_reranking,
                enable_hybrid=getattr(
                    adv_settings, "enable_hybrid", adv_settings.enable_hybrid_search
                ),
                enable_expansion=getattr(
                    adv_settings,
                    "enable_expansion",
                    adv_settings.enable_query_expansion,
                ),
                # Reranking settings
                reranker_model=adv_settings.reranker_model,
                reranker_threshold=adv_settings.reranker_threshold,
                # Hybrid search settings
                hybrid_alpha=adv_settings.hybrid_alpha,
                keyword_search_enabled=adv_settings.keyword_search_enabled,
                # Query expansion settings
                expansion_type=adv_settings.expansion_type,
                max_expanded_queries=adv_settings.max_expanded_queries,
                # Advanced settings
                confidence_threshold=adv_settings.confidence_threshold,
                initial_search_multiplier=adv_settings.initial_search_multiplier,
            )

            logger.info("Advanced retriever initialized successfully")
            return advanced_retriever

        except Exception as e:
            logger.warning(f"Failed to initialize advanced retriever: {e}")
            return None

    def _initialize_semantic_cache(self):
        """Initialize semantic cache with settings."""
        try:
            from ragbot.caching.adaptive_cache import AdaptiveCache

            # Get settings
            cache_settings = settings.semantic_cache

            # Initialize semantic cache
            semantic_cache = AdaptiveCache(
                similarity_threshold=cache_settings.similarity_threshold,
                max_size=cache_settings.max_size,
                ttl_seconds=cache_settings.ttl_seconds,
                embedder=self.embedder,
                eviction_strategy=cache_settings.eviction_strategy,
            )

            logger.info("Semantic cache initialized successfully")
            return semantic_cache

        except Exception as e:
            logger.warning(f"Failed to initialize semantic cache: {e}")
            return None

    # Analytics methods
    async def get_analytics_report(self, days: int = 30) -> Dict[str, Any]:
        """دریافت گزارش تحلیل"""
        try:
            return await self.analytics_dashboard.get_analytics_report(days)
        except Exception as e:
            logger.error(f"Error getting analytics report: {e}")
            return {"error": str(e)}

    async def get_ml_insights(self) -> Dict[str, Any]:
        """دریافت بینش‌های ML"""
        try:
            return await self.analytics_dashboard.get_ml_insights()
        except Exception as e:
            logger.error(f"Error getting ML insights: {e}")
            return {"error": str(e)}

    async def get_predictive_analytics(self) -> Dict[str, Any]:
        """دریافت تحلیل‌های پیش‌بینانه"""
        try:
            return await self.analytics_dashboard.get_predictive_analytics()
        except Exception as e:
            logger.error(f"Error getting predictive analytics: {e}")
            return {"error": str(e)}

    async def get_advanced_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """دریافت تحلیل‌های پیشرفته کاربر"""
        try:
            return await self.analytics_dashboard.get_advanced_user_analytics(user_id)
        except Exception as e:
            logger.error(f"Error getting advanced user analytics: {e}")
            return {"error": str(e)}

    async def get_comprehensive_analytics_report(
        self, days: int = 30
    ) -> Dict[str, Any]:
        """دریافت گزارش جامع تحلیل"""
        try:
            return await self.analytics_dashboard.get_comprehensive_analytics_report(
                days
            )
        except Exception as e:
            logger.error(f"Error getting comprehensive analytics report: {e}")
            return {"error": str(e)}

    async def track_user_action(
        self, user_id: str, action: str, metadata: Dict[str, Any] = None
    ):
        """ردیابی عمل کاربر"""
        try:
            await self.analytics_dashboard.track_user_action(user_id, action, metadata)
        except Exception as e:
            logger.error(f"Error tracking user action: {e}")

    async def record_satisfaction_feedback(
        self,
        user_id: str,
        query: str,
        response: str,
        satisfaction_score: float,
        feedback: str = "",
    ):
        """ثبت بازخورد رضایت کاربر"""
        try:
            await self.analytics_dashboard.record_satisfaction_feedback(
                user_id, query, response, satisfaction_score, feedback
            )
        except Exception as e:
            logger.error(f"Error recording satisfaction feedback: {e}")

    # Aliases for API and CLI compatibility
    query = query_documents
    reset_vector_store = reset_store

    # Multi-tenant forwarding methods
    async def create_tenant(
        self,
        name: str,
        tier: str = "free",
        plan: str = "trial",
        domain: Optional[str] = None,
        contact_email: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create new tenant"""
        try:
            if not self.tenant_manager:
                return {"error": "Multi-tenant support is disabled"}

            tenant_config = await self.tenant_manager.create_tenant(
                name=name,
                tier=TenantTier(tier),
                plan=TenantPlan(plan),
                domain=domain,
                contact_email=contact_email,
                tenant_id=tenant_id,
            )

            return {
                "success": True,
                "tenant_id": tenant_config.tenant_id,
                "name": tenant_config.name,
                "tier": tenant_config.tier.value
                if hasattr(tenant_config.tier, "value")
                else str(tenant_config.tier),
                "plan": tenant_config.plan.value
                if hasattr(tenant_config.plan, "value")
                else str(tenant_config.plan),
            }
        except Exception as e:
            logger.error(f"Error creating tenant: {e}")
            return {"error": str(e)}

    async def get_tenant_info(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant info"""
        try:
            if not self.tenant_manager:
                return {"error": "Multi-tenant support is disabled"}

            tenant = await self.tenant_manager.get_tenant(tenant_id)
            if not tenant:
                return {"error": "Tenant not found"}

            return {
                "tenant_id": tenant.tenant_id,
                "name": tenant.name,
                "tier": tenant.tier.value
                if hasattr(tenant.tier, "value")
                else str(tenant.tier),
                "plan": tenant.plan.value
                if hasattr(tenant.plan, "value")
                else str(tenant.plan),
                "status": tenant.status.value
                if hasattr(tenant.status, "value")
                else str(tenant.status),
                "created_at": tenant.created_at.isoformat()
                if hasattr(tenant.created_at, "isoformat")
                else str(tenant.created_at),
                "expires_at": tenant.expires_at.isoformat()
                if tenant.expires_at and hasattr(tenant.expires_at, "isoformat")
                else None,
                "limits": {
                    "max_documents": tenant.limits.max_documents,
                    "max_queries_per_day": tenant.limits.max_queries_per_day,
                    "max_storage_gb": tenant.limits.max_storage_gb,
                    "max_users": tenant.limits.max_users,
                },
                "features": {
                    "advanced_analytics": tenant.features.advanced_analytics,
                    "ml_insights": tenant.features.ml_insights,
                    "predictive_analytics": tenant.features.predictive_analytics,
                    "api_access": tenant.features.api_access,
                },
            }
        except Exception as e:
            logger.error(f"Error getting tenant info: {e}")
            return {"error": str(e)}

    async def get_tenant_analytics(
        self, tenant_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get tenant analytics dashboard"""
        try:
            if not self.tenant_analytics:
                return {"error": "Multi-tenant support is disabled"}

            return await self.tenant_analytics.get_tenant_dashboard(tenant_id)
        except Exception as e:
            logger.error(f"Error getting tenant analytics: {e}")
            return {"error": str(e)}

    async def get_tenant_usage_trends(
        self,
        tenant_id: str,
        days: int = 30,
        metric: str = "queries",
    ) -> Dict[str, Any]:
        """Get tenant usage trends"""
        try:
            if not self.tenant_analytics:
                return {"error": "Multi-tenant support is disabled"}

            return await self.tenant_analytics.get_usage_trends(
                tenant_id, days, metric
            )
        except Exception as e:
            logger.error(f"Error getting tenant usage trends: {e}")
            return {"error": str(e)}

    async def get_tenant_security_report(
        self,
        tenant_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get tenant security report"""
        try:
            if not self.tenant_analytics:
                return {"error": "Multi-tenant support is disabled"}

            return await self.tenant_analytics.get_security_report(tenant_id, days)
        except Exception as e:
            logger.error(f"Error getting tenant security report: {e}")
            return {"error": str(e)}

    async def create_tenant_user(
        self,
        tenant_id: str,
        username: str,
        email: str,
        password: str,
        role: str = "user",
    ) -> Dict[str, Any]:
        """Create tenant user"""
        try:
            if not self.tenant_auth:
                return {"error": "Multi-tenant support is disabled"}

            from ragbot.multi_tenant.tenant_auth import UserRole

            success, user, error = await self.tenant_auth.create_user(
                tenant_id=tenant_id,
                username=username,
                email=email,
                password=password,
                role=UserRole(role),
            )

            if success:
                return {
                    "success": True,
                    "user_id": user.user_id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value
                    if hasattr(user.role, "value")
                    else str(user.role),
                }
            else:
                return {"error": error}
        except Exception as e:
            logger.error(f"Error creating tenant user: {e}")
            return {"error": str(e)}

    async def authenticate_tenant_user(
        self,
        tenant_id: str,
        username: str,
        password: str,
    ) -> Dict[str, Any]:
        """Authenticate tenant user"""
        try:
            if not self.tenant_auth:
                return {"error": "Multi-tenant support is disabled"}

            success, user, session_token = (
                await self.tenant_auth.authenticate_user(
                    tenant_id=tenant_id,
                    username=username,
                    password=password,
                )
            )

            if success:
                return {
                    "success": True,
                    "user_id": user.user_id,
                    "username": user.username,
                    "role": user.role.value
                    if hasattr(user.role, "value")
                    else str(user.role),
                    "session_token": session_token,
                }
            else:
                return {"error": session_token}
        except Exception as e:
            logger.error(f"Error authenticating tenant user: {e}")
            return {"error": str(e)}

    async def create_tenant_api_key(
        self,
        tenant_id: str,
        name: str = "default",
        user_id: Optional[str] = None,
        expires_days: int = 365,
        permissions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new API key for a tenant."""
        try:
            if not self.tenant_auth:
                return {"error": "Multi-tenant support is disabled"}

            success, raw_key, error = await self.tenant_auth.create_api_key(
                tenant_id=tenant_id,
                user_id=user_id,
                name=name,
                expires_days=expires_days,
                permissions=permissions,
            )
            if success:
                return {
                    "success": True,
                    "tenant_id": tenant_id,
                    "name": name,
                    "api_key": raw_key,
                    "prefix": raw_key[:12] if raw_key else "",
                    "expires_days": expires_days,
                }
            return {"error": error or "Failed to create API key"}
        except Exception as e:
            logger.error(f"Error creating tenant API key: {e}")
            return {"error": str(e)}

    async def revoke_tenant_api_key(
        self,
        tenant_id: str,
        api_key_or_id: str,
        revoked_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Revoke a tenant API key."""
        try:
            if not self.tenant_auth:
                return {"error": "Multi-tenant support is disabled"}

            success = await self.tenant_auth.revoke_api_key(
                tenant_id=tenant_id,
                api_key_or_id=api_key_or_id,
                revoked_by=revoked_by,
            )
            if success:
                return {"success": True, "message": "API key revoked successfully"}
            return {"error": "API key not found or already revoked"}
        except Exception as e:
            logger.error(f"Error revoking tenant API key: {e}")
            return {"error": str(e)}

    async def list_tenant_api_keys(self, tenant_id: str) -> Dict[str, Any]:
        """List active API keys for a tenant without exposing secret hashes."""
        try:
            if not self.tenant_auth:
                return {"error": "Multi-tenant support is disabled"}

            keys = await self.tenant_auth.list_api_keys(tenant_id)
            return {"success": True, "tenant_id": tenant_id, "api_keys": keys}
        except Exception as e:
            logger.error(f"Error listing tenant API keys: {e}")
            return {"error": str(e)}


