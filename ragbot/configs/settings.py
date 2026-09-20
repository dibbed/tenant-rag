"""
Configuration management using Pydantic Settings for the RAG Telegram bot.

This module provides comprehensive configuration management with environment variable
support, validation, and type safety using Pydantic Settings.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings as PydanticBaseSettings, SettingsConfigDict


class VectorStoreConfig(PydanticBaseSettings):
    """Advanced configuration for vector store selection and settings."""

    # Store selection
    default_store: str = Field(default="faiss", description="Default vector store type")
    available_stores: List[str] = Field(
        default=["faiss", "chroma", "qdrant", "weaviate"],
        description="Available vector store types",
    )

    # Advanced features
    enable_metadata_filtering: bool = Field(
        default=True, description="Enable metadata filtering"
    )
    enable_semantic_chunking: bool = Field(
        default=True, description="Enable semantic chunking"
    )
    enable_hybrid_search: bool = Field(default=True, description="Enable hybrid search")
    enable_reranking: bool = Field(default=True, description="Enable reranking")
    enable_analytics: bool = Field(default=True, description="Enable analytics")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")

    # Advanced query features
    enable_advanced_queries: bool = Field(
        default=True, description="Enable advanced query features"
    )
    enable_aggregation: bool = Field(
        default=True, description="Enable query aggregation"
    )
    enable_custom_scoring: bool = Field(
        default=True, description="Enable custom scoring"
    )
    enable_query_optimization: bool = Field(
        default=True, description="Enable query optimization"
    )

    # Advanced Analytics features
    enable_ml_insights: bool = Field(
        default=True, description="Enable ML insights engine"
    )
    enable_predictive_analytics: bool = Field(
        default=True, description="Enable predictive analytics"
    )
    enable_user_segmentation: bool = Field(
        default=True, description="Enable user segmentation"
    )
    enable_churn_prediction: bool = Field(
        default=True, description="Enable churn prediction"
    )
    enable_personalization: bool = Field(
        default=True, description="Enable personalization recommendations"
    )
    enable_anomaly_detection: bool = Field(
        default=True, description="Enable anomaly detection"
    )

    # Security features
    enable_encryption: bool = Field(default=True, description="Enable data encryption")
    enable_secure_backup: bool = Field(default=True, description="Enable secure backup")
    enable_key_rotation: bool = Field(default=True, description="Enable key rotation")

    # Advanced query features
    enable_advanced_filtering: bool = Field(
        default=True, description="Enable advanced filtering"
    )

    # FAISS settings with advanced options
    faiss_index_type: str = Field(default="flat", description="FAISS index type")
    faiss_similarity_metric: str = Field(
        default="cosine", description="FAISS similarity metric"
    )
    faiss_nlist: int = Field(default=100, description="FAISS nlist parameter")
    faiss_nprobe: int = Field(default=10, description="FAISS nprobe parameter")
    faiss_hnsw_m: int = Field(default=16, description="FAISS HNSW M parameter")
    faiss_hnsw_ef_construction: int = Field(
        default=200, description="FAISS HNSW ef_construction"
    )
    faiss_hnsw_ef_search: int = Field(default=50, description="FAISS HNSW ef_search")
    faiss_enable_gpu: bool = Field(
        default=False, description="Enable FAISS GPU support"
    )
    faiss_gpu_id: int = Field(default=0, description="FAISS GPU ID")

    # Chroma settings with advanced features
    chroma_persist_directory: str = Field(
        default="./chroma_db", description="Chroma persist directory"
    )
    chroma_collection_name: str = Field(
        default="ragbot", description="Chroma collection name"
    )
    chroma_distance_function: str = Field(
        default="cosine", description="Chroma distance function"
    )
    chroma_hnsw_space: str = Field(default="cosine", description="Chroma HNSW space")
    chroma_hnsw_construction_ef: int = Field(
        default=200, description="Chroma HNSW construction ef"
    )
    chroma_hnsw_search_ef: int = Field(default=50, description="Chroma HNSW search ef")
    chroma_hnsw_m: int = Field(default=16, description="Chroma HNSW M parameter")
    chroma_enable_metadata_filtering: bool = Field(
        default=True, description="Enable Chroma metadata filtering"
    )
    chroma_enable_hybrid_search: bool = Field(
        default=True, description="Enable Chroma hybrid search"
    )
    chroma_enable_reranking: bool = Field(
        default=True, description="Enable Chroma reranking"
    )

    # Qdrant settings with advanced features
    qdrant_url: str = Field(
        default="http://localhost:6333", description="Qdrant server URL"
    )
    qdrant_collection_name: str = Field(
        default="ragbot", description="Qdrant collection name"
    )
    qdrant_vector_size: int = Field(default=1536, description="Qdrant vector size")
    qdrant_timeout: int = Field(default=30, description="Qdrant timeout in seconds")
    qdrant_enable_payload_indexing: bool = Field(
        default=True, description="Enable Qdrant payload indexing"
    )
    qdrant_enable_hnsw_index: bool = Field(
        default=True, description="Enable Qdrant HNSW index"
    )
    qdrant_hnsw_m: int = Field(default=16, description="Qdrant HNSW M parameter")
    qdrant_hnsw_ef_construction: int = Field(
        default=200, description="Qdrant HNSW ef_construction"
    )
    qdrant_hnsw_ef_search: int = Field(default=50, description="Qdrant HNSW ef_search")
    qdrant_enable_metadata_filtering: bool = Field(
        default=True, description="Enable Qdrant metadata filtering"
    )
    qdrant_enable_hybrid_search: bool = Field(
        default=True, description="Enable Qdrant hybrid search"
    )
    qdrant_enable_reranking: bool = Field(
        default=True, description="Enable Qdrant reranking"
    )

    # Weaviate settings (future)
    weaviate_url: str = Field(
        default="http://localhost:8080", description="Weaviate server URL"
    )
    weaviate_class_name: str = Field(
        default="RagBot", description="Weaviate class name"
    )
    weaviate_api_key: Optional[str] = Field(
        default=None, description="Weaviate API key"
    )
    weaviate_enable_graphql: bool = Field(
        default=True, description="Enable Weaviate GraphQL"
    )
    weaviate_enable_multi_modal: bool = Field(
        default=False, description="Enable Weaviate multi-modal"
    )

    # Advanced chunking settings
    chunking_strategy: str = Field(default="semantic", description="Chunking strategy")
    semantic_chunking_model: str = Field(
        default="all-MiniLM-L6-v2", description="Semantic chunking model"
    )
    semantic_chunking_threshold: float = Field(
        default=0.7, description="Semantic chunking threshold"
    )
    semantic_chunking_max_chunk_size: int = Field(
        default=512, description="Semantic chunking max chunk size"
    )
    semantic_chunking_overlap: int = Field(
        default=50, description="Semantic chunking overlap"
    )

    # Token chunking settings
    token_chunking_max_tokens: int = Field(
        default=512, description="Token chunking max tokens"
    )
    token_chunking_overlap: int = Field(
        default=50, description="Token chunking overlap"
    )
    token_chunking_model: str = Field(
        default="gpt-3.5-turbo", description="Token chunking model"
    )

    # Hierarchical chunking settings
    hierarchical_chunking_max_chunk_size: int = Field(
        default=512, description="Hierarchical chunking max chunk size"
    )
    hierarchical_chunking_overlap: int = Field(
        default=50, description="Hierarchical chunking overlap"
    )
    hierarchical_chunking_min_chunk_size: int = Field(
        default=100, description="Hierarchical chunking min chunk size"
    )

    # Adaptive chunking settings
    adaptive_chunking_min_chunk_size: int = Field(
        default=100, description="Adaptive chunking min chunk size"
    )
    adaptive_chunking_max_chunk_size: int = Field(
        default=512, description="Adaptive chunking max chunk size"
    )
    adaptive_chunking_overlap: int = Field(
        default=50, description="Adaptive chunking overlap"
    )
    adaptive_chunking_threshold: float = Field(
        default=0.7, description="Adaptive chunking threshold"
    )

    # Advanced embedding settings
    embedding_provider: str = Field(
        default="sentence_transformers", description="Embedding provider"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2", description="Embedding model"
    )
    embedding_dimension: int = Field(default=384, description="Embedding dimension")
    embedding_batch_size: int = Field(default=100, description="Embedding batch size")
    embedding_max_retries: int = Field(default=3, description="Embedding max retries")
    embedding_timeout: float = Field(default=30.0, description="Embedding timeout")
    embedding_enable_caching: bool = Field(
        default=True, description="Enable embedding caching"
    )
    embedding_cache_ttl: int = Field(default=3600, description="Embedding cache TTL")

    # OpenAI embedding settings
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )
    openai_embedding_dimension: int = Field(
        default=1536, description="OpenAI embedding dimension"
    )
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_base_url: Optional[str] = Field(default=None, description="OpenAI base URL")

    # HuggingFace embedding settings
    huggingface_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="HuggingFace model",
    )
    huggingface_device: str = Field(default="cpu", description="HuggingFace device")
    huggingface_trust_remote_code: bool = Field(
        default=False, description="HuggingFace trust remote code"
    )

    # Advanced retrieval settings
    retrieval_strategy: str = Field(default="hybrid", description="Retrieval strategy")
    retrieval_top_k: int = Field(default=10, description="Retrieval top k")
    retrieval_similarity_threshold: float = Field(
        default=0.7, description="Retrieval similarity threshold"
    )
    retrieval_enable_reranking: bool = Field(
        default=True, description="Enable retrieval reranking"
    )
    retrieval_reranking_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2", description="Reranking model"
    )
    retrieval_reranking_top_k: int = Field(default=20, description="Reranking top k")

    # Hybrid search settings
    hybrid_search_alpha: float = Field(
        default=0.7, description="Hybrid search alpha weight"
    )
    hybrid_search_enable_keyword_search: bool = Field(
        default=True, description="Enable keyword search"
    )
    hybrid_search_keyword_weight: float = Field(
        default=0.3, description="Keyword search weight"
    )
    hybrid_search_semantic_weight: float = Field(
        default=0.7, description="Semantic search weight"
    )

    # Prompt engineering settings
    prompt_template: str = Field(default="default", description="Prompt template")
    prompt_max_context_length: int = Field(
        default=4000, description="Prompt max context length"
    )
    prompt_enable_few_shot: bool = Field(
        default=True, description="Enable few-shot prompting"
    )
    prompt_few_shot_examples: int = Field(
        default=3, description="Number of few-shot examples"
    )
    prompt_enable_chain_of_thought: bool = Field(
        default=True, description="Enable chain of thought prompting"
    )
    prompt_enable_self_reflection: bool = Field(
        default=False, description="Enable self-reflection prompting"
    )

    # Performance and monitoring settings
    enable_performance_monitoring: bool = Field(
        default=True, description="Enable performance monitoring"
    )
    enable_quality_evaluation: bool = Field(
        default=True, description="Enable quality evaluation"
    )
    enable_user_analytics: bool = Field(
        default=True, description="Enable user analytics"
    )
    enable_error_tracking: bool = Field(
        default=True, description="Enable error tracking"
    )
    enable_metrics_collection: bool = Field(
        default=True, description="Enable metrics collection"
    )

    # Security settings
    enable_content_filtering: bool = Field(
        default=True, description="Enable content filtering"
    )
    enable_input_validation: bool = Field(
        default=True, description="Enable input validation"
    )
    enable_output_sanitization: bool = Field(
        default=True, description="Enable output sanitization"
    )
    enable_rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests_per_minute: int = Field(
        default=60, description="Rate limit requests per minute"
    )
    rate_limit_requests_per_hour: int = Field(
        default=1000, description="Rate limit requests per hour"
    )

    @field_validator("default_store")
    def validate_default_store(cls, v):
        """Validate default store type."""
        valid_stores = ["faiss", "chroma", "qdrant"]
        if v not in valid_stores:
            raise ValueError(f"default_store must be one of {valid_stores}")
        return v

    @field_validator("chunking_strategy")
    def validate_chunking_strategy(cls, v):
        """Validate chunking strategy."""
        valid_strategies = ["semantic", "token", "hierarchical", "adaptive"]
        if v not in valid_strategies:
            raise ValueError(f"chunking_strategy must be one of {valid_strategies}")
        return v

    @field_validator("embedding_provider")
    def validate_embedding_provider(cls, v):
        """Validate embedding provider."""
        valid_providers = ["sentence_transformers", "openai", "huggingface"]
        if v not in valid_providers:
            raise ValueError(f"embedding_provider must be one of {valid_providers}")
        return v

    @field_validator("retrieval_strategy")
    def validate_retrieval_strategy(cls, v):
        """Validate retrieval strategy."""
        valid_strategies = ["semantic", "keyword", "hybrid"]
        if v not in valid_strategies:
            raise ValueError(f"retrieval_strategy must be one of {valid_strategies}")
        return v

    model_config = SettingsConfigDict(
        env_prefix="VECTOR_STORE_",
        extra="ignore",
    )


class DatabaseSettings(PydanticBaseSettings):
    """Database configuration settings."""

    url: str = Field(default="sqlite:///./data/ragbot.db", description="Database URL")
    echo: bool = Field(default=False, description="Enable SQL query logging")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max connection overflow")

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        extra="ignore",
    )


class RedisSettings(PydanticBaseSettings):
    """Redis configuration settings."""

    url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    max_connections: int = Field(default=10, description="Max Redis connections")
    socket_timeout: float = Field(default=5.0, description="Socket timeout in seconds")

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        extra="ignore",
    )


class PluginSettings(PydanticBaseSettings):
    """Plugin system configuration settings."""

    directory: str = Field(default="plugins", description="Plugin directory path")
    auto_load: bool = Field(
        default=False, description="Automatically load plugins on startup"
    )
    enable_hotswap: bool = Field(
        default=True, description="Enable hot-swapping of plugins"
    )
    validate_security: bool = Field(
        default=True, description="Enable plugin security validation"
    )
    allowed_imports: List[str] = Field(
        default=[
            "ragbot",
            "typing",
            "datetime",
            "pathlib",
            "dataclasses",
            "abc",
            "asyncio",
            "json",
            "logging",
            "collections",
            "statistics",
        ],
        description="List of allowed Python imports in plugins",
    )
    banned_functions: List[str] = Field(
        default=[
            "eval",
            "exec",
            "__import__",
            "compile",
            "open",
            "input",
            "raw_input",
            "execfile",
            "file",
            "apply",
        ],
        description="List of banned function calls in plugins",
    )
    marketplace_url: str = Field(
        default="https://api.ragbot-marketplace.com",
        description="Plugin marketplace API URL",
    )
    cache_directory: str = Field(
        default="plugins/marketplace", description="Marketplace cache directory"
    )
    max_plugins: int = Field(
        default=50, description="Maximum number of plugins allowed"
    )

    model_config = SettingsConfigDict(
        env_prefix="PLUGIN_",
        extra="ignore",
    )


class SemanticCacheSettings(PydanticBaseSettings):
    """تنظیمات کش معنایی"""

    # Cache configuration
    enable_semantic_cache: bool = Field(
        default=True, description="Enable semantic cache"
    )
    similarity_threshold: float = Field(
        default=0.8, description="Cache similarity threshold"
    )
    max_size: int = Field(default=1000, description="Maximum cache size")
    ttl_seconds: int = Field(default=3600, description="Cache TTL in seconds")
    enable_query_cache: bool = Field(
        default=True, description="Enable exact query result caching"
    )

    # Eviction strategy
    eviction_strategy: str = Field(
        default="adaptive", description="Eviction strategy (lru, lfu, adaptive)"
    )
    eviction_threshold: float = Field(default=0.9, description="Eviction threshold")

    # Performance optimization
    enable_cache_metrics: bool = Field(default=True, description="Enable cache metrics")
    cleanup_interval: int = Field(
        default=300, description="Cache cleanup interval in seconds"
    )
    export_enabled: bool = Field(default=False, description="Enable cache export")

    # Advanced features
    enable_adaptive_sizing: bool = Field(
        default=True, description="Enable adaptive cache sizing"
    )
    enable_quality_scoring: bool = Field(
        default=True, description="Enable quality scoring"
    )
    enable_access_pattern_analysis: bool = Field(
        default=True, description="Enable access pattern analysis"
    )

    # Monitoring
    monitoring_enabled: bool = Field(
        default=True, description="Enable cache monitoring"
    )
    alert_thresholds: Dict[str, float] = Field(
        default={
            "hit_rate_min": 0.6,
            "response_time_max": 0.1,
            "memory_usage_max": 0.8,
        },
        description="Cache alert thresholds",
    )

    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        extra="ignore",
    )


class AdvancedRetrievalSettings(PydanticBaseSettings):
    """تنظیمات جستجوی پیشرفته"""

    # Reranking settings
    enable_reranking: bool = Field(default=True, description="Enable reranking")
    reranker_model: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2", description="Reranker model"
    )
    reranker_threshold: float = Field(default=0.7, description="Reranker threshold")
    rerank_timeout: float = Field(
        default=30.0, description="Reranking timeout in seconds"
    )

    # Advanced reranking settings
    enable_metadata_scoring: bool = Field(
        default=True, description="Enable metadata-based scoring in reranking"
    )
    rerank_batch_size: int = Field(
        default=32, description="Batch size for reranking operations"
    )
    rerank_max_documents: int = Field(
        default=100, description="Maximum documents to rerank"
    )
    metadata_weight: float = Field(
        default=0.2, description="Weight for metadata in combined scoring"
    )
    rerank_cache_size: int = Field(
        default=50, description="Maximum size of reranking cache"
    )

    # Hybrid search settings
    enable_hybrid: bool = Field(default=True, description="Enable hybrid search")
    enable_hybrid_search: bool = Field(
        default=True, description="Enable hybrid search (legacy)"
    )
    hybrid_alpha: float = Field(default=0.7, description="Weight for semantic search")
    hybrid_default_alpha: float = Field(
        default=0.7, description="Default alpha for hybrid search"
    )
    keyword_search_enabled: bool = Field(
        default=True, description="Enable keyword search"
    )
    min_hybrid_score: float = Field(
        default=0.0, description="Minimum hybrid score threshold"
    )

    # Query expansion settings
    enable_expansion: bool = Field(default=True, description="Enable query expansion")
    enable_query_expansion: bool = Field(
        default=True, description="Enable query expansion (legacy)"
    )
    expansion_type: str = Field(default="synonym", description="Expansion type")
    max_expanded_queries: int = Field(default=3, description="Max expanded queries")
    expansion_timeout: float = Field(
        default=10.0, description="Query expansion timeout in seconds"
    )

    # AI expansion settings
    enable_ai_expansion: bool = Field(
        default=False, description="Enable AI-based query expansion"
    )
    synonym_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        description="Synonym generation model",
    )

    # Expansion cache settings
    expansion_cache_size: int = Field(
        default=100, description="Maximum size of expansion cache"
    )
    min_query_length: int = Field(
        default=3, description="Minimum query length for expansion"
    )

    # Advanced retrieval settings
    initial_search_multiplier: int = Field(
        default=2, description="Multiplier for initial search"
    )
    confidence_threshold: float = Field(default=0.5, description="Confidence threshold")

    # Content deduplication settings
    enable_content_dedup: bool = Field(
        default=True, description="Enable content-based deduplication"
    )
    content_dedup_threshold: float = Field(
        default=0.95, description="Content similarity threshold for deduplication"
    )

    # Caching settings
    query_cache_size: int = Field(
        default=100, description="Maximum size of query expansion cache"
    )

    model_config = SettingsConfigDict(
        env_prefix="ADVANCED_RETRIEVAL_",
        extra="ignore",
    )


class LLMSettings(PydanticBaseSettings):
    """LLM provider configuration settings."""

    provider: Literal["openai", "anthropic", "ollama", "openrouter", "hf_local"] = (
        Field(default="openrouter", description="LLM provider")
    )
    model: str = Field(default="x-ai/grok-4-fast:free", description="LLM model name")
    max_tokens: Optional[int] = Field(
        default=None, description="Maximum tokens in response (None = model decides)"
    )
    temperature: float = Field(default=0.3, description="LLM temperature")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    # Optional base URL (e.g., OpenRouter, custom gateways)
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    # HF local (transformers) options
    hf_model: Optional[str] = Field(
        default=None, description="Hugging Face local model id"
    )
    hf_device: Optional[str] = Field(
        default=None, description="Device for HF model (cpu/cuda/auto)"
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate LLM provider."""
        allowed = ["openai", "anthropic", "ollama", "openrouter", "hf_local"]
        if v not in allowed:
            raise ValueError(f"Provider must be one of {allowed}")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        extra="ignore",
    )


class EmbeddingSettings(PydanticBaseSettings):
    """Embedding configuration settings."""

    provider: Literal["openai", "huggingface", "sentence_transformers"] = Field(
        default="openai", description="Embedding provider"
    )
    model: str = Field(
        default="text-embedding-ada-002", description="Embedding model name"
    )
    batch_size: int = Field(default=100, description="Embedding batch size")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    # Optional advanced toggles
    enable_cache: bool = Field(
        default=True, description="Enable embedding cache lookups"
    )
    # Local cache directory for SentenceTransformers/HuggingFace models
    cache_folder: str = Field(
        default="./cache/sentence_transformers",
        description="Local cache folder for sentence-transformers models",
    )

    model_config = SettingsConfigDict(
        env_prefix="EMBED_",
        extra="ignore",
    )


class RetrieveSettings(PydanticBaseSettings):
    """تنظیمات جستجو و بازیابی"""

    # Hybrid search settings
    hybrid_default_alpha: float = Field(
        default=0.7, description="Default alpha for hybrid search"
    )
    min_hybrid_score: float = Field(
        default=0.0, description="Minimum hybrid score threshold"
    )

    model_config = SettingsConfigDict(
        env_prefix="RETRIEVE_",
        extra="ignore",
    )


class StoreSettings(PydanticBaseSettings):
    """FAISS/Store configuration settings."""

    similarity_metric: Literal["cosine", "ip", "l2"] = Field(
        default="cosine", description="Similarity metric for vector store"
    )
    faiss_nlist: int = Field(default=100, description="FAISS IVF nlist (clusters)")
    faiss_nprobe: int = Field(
        default=10, description="FAISS IVF nprobe (search probes)"
    )
    faiss_hnsw_m: int = Field(default=16, description="FAISS HNSW M (connections)")
    faiss_hnsw_ef_search: Optional[int] = Field(
        default=None, description="FAISS HNSW efSearch (search breadth)"
    )
    store_keep_embeddings: bool = Field(
        default=True,
        description="Keep embeddings in memory/on disk alongside FAISS index",
    )
    store_path: str = Field(default="./data/vector_store", description="Store path")

    # Chroma-specific (optional)
    chroma_persist_directory: str = Field(
        default="./data/vector_store/chroma", description="Chroma persist directory"
    )
    chroma_collection_name: str = Field(
        default="ragbot", description="Chroma collection name"
    )
    chroma_distance_function: Literal["cosine", "l2", "ip"] = Field(
        default="cosine", description="Chroma distance/similarity function"
    )

    # Qdrant-specific (optional)
    qdrant_url: str = Field(
        default="http://localhost:6333", description="Qdrant endpoint URL"
    )
    qdrant_path: Optional[str] = Field(
        default="./data/vector_store/qdrant",
        description="Optional local path for Qdrant client",
    )
    qdrant_collection_name: str = Field(
        default="ragbot", description="Qdrant collection name"
    )
    qdrant_vector_size: int = Field(
        default=1536, description="Qdrant vector size (embedding dimension)"
    )
    qdrant_timeout: int = Field(default=30, description="Qdrant client timeout (s)")

    # Weaviate-specific (optional)
    weaviate_url: str = Field(
        default="http://localhost:8080", description="Weaviate endpoint URL"
    )
    weaviate_api_key: Optional[str] = Field(
        default=None, description="Weaviate API key (if required)"
    )
    weaviate_class_name: str = Field(
        default="Document", description="Weaviate class name"
    )
    weaviate_vector_size: int = Field(
        default=1536, description="Weaviate vector size (embedding dimension)"
    )
    weaviate_timeout: int = Field(default=30, description="Weaviate client timeout (s)")

    # Batch sizes for bulk operations
    chroma_batch_size: int = Field(
        default=1000, description="Batch size for Chroma upserts"
    )
    qdrant_batch_size: int = Field(
        default=1000, description="Batch size for Qdrant upserts"
    )
    weaviate_batch_size: int = Field(
        default=1000, description="Batch size for Weaviate upserts"
    )

    model_config = SettingsConfigDict(
        env_prefix="STORE_",
        extra="ignore",
    )


class RAGSettings(PydanticBaseSettings):
    """RAG system configuration settings."""

    chunk_size: int = Field(default=512, description="Text chunk size in tokens")
    chunk_overlap: int = Field(default=50, description="Chunk overlap in tokens")
    top_k: int = Field(default=4, description="Number of retrieved chunks")
    similarity_threshold: float = Field(
        default=0.7, description="Minimum similarity threshold"
    )
    max_chunks_per_document: int = Field(
        default=1000, description="Maximum chunks per document"
    )
    # OCR / extraction configuration
    ocr_enabled: bool = Field(default=False, description="Enable OCR on images in PDFs")
    ocr_engine: Literal["none", "pytesseract", "easyocr", "google"] = Field(
        default="none", description="OCR engine to use"
    )
    ocr_lang: str = Field(default="eng", description="OCR language code")
    google_token_path: Optional[str] = Field(
        default=None, description="Path to Google OAuth token.json for Drive OCR"
    )

    @field_validator("chunk_size")
    @classmethod
    def validate_chunk_size(cls, v: int) -> int:
        """Validate chunk size."""
        if v <= 0 or v > 2000:
            raise ValueError("Chunk size must be between 1 and 2000")
        return v

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        """Validate top_k value."""
        if v <= 0 or v > 20:
            raise ValueError("top_k must be between 1 and 20")
        return v

    @field_validator("ocr_engine")
    @classmethod
    def validate_ocr_engine(cls, v: str) -> str:
        allowed = {"none", "pytesseract", "easyocr", "google"}
        if v not in allowed:
            raise ValueError(f"ocr_engine must be one of {sorted(allowed)}")
        return v

    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        extra="ignore",
    )


class SecuritySettings(PydanticBaseSettings):
    """Security configuration settings."""

    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")
    allowed_file_types: List[str] = Field(
        default=[
            "pdf",
            "txt",
            "docx",
            "html",
            "pptx",
            "xlsx",
            "md",
            "png",
            "jpg",
            "jpeg",
            "tiff",
            "bmp",
        ],
        description="Allowed file types",
    )
    rate_limit_requests: int = Field(
        default=10, description="Rate limit requests per window"
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds"
    )
    # Content filtering toggles
    content_filter_strict_mode: bool = Field(
        default=False, description="Enable strict mode for filtering"
    )
    auto_block_repeat_offenders: bool = Field(
        default=True, description="Auto-block users after repeated violations"
    )
    max_filtered_messages: int = Field(
        default=3, description="Threshold to block users automatically"
    )
    enable_user_allowlist: bool = Field(
        default=True, description="Enable user allowlist"
    )

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        extra="ignore",
    )


class MultiFormatSettings(PydanticBaseSettings):
    """تنظیمات پشتیبانی چندفرمت"""

    # فرمت‌های پشتیبانی شده (از SecuritySettings استفاده می‌شود)
    # supported_formats: List[str] = Field(...)  # حذف شد - از SecuritySettings استفاده می‌شود

    # تنظیمات OCR
    ocr_enabled: bool = Field(default=True, description="Enable OCR processing")
    ocr_language: str = Field(
        default="fas+eng", description="OCR language (Persian + English)"
    )
    ocr_confidence_threshold: float = Field(
        default=0.6, description="OCR confidence threshold"
    )

    # تنظیمات Excel
    excel_max_rows: int = Field(
        default=1000, description="Maximum rows to process from Excel"
    )
    excel_include_headers: bool = Field(
        default=True, description="Include headers in Excel processing"
    )
    excel_max_sheets: int | None = Field(
        default=None, description="Optional cap on number of sheets to process"
    )
    xlsx_detect_language: bool = Field(
        default=False, description="Detect language for XLSX text (3-segment voting)"
    )

    # تنظیمات PowerPoint
    pptx_extract_images: bool = Field(
        default=False, description="Extract images from PowerPoint"
    )
    pptx_extract_notes: bool = Field(
        default=True, description="Extract notes from PowerPoint"
    )

    # تنظیمات HTML
    html_extract_links: bool = Field(
        default=True, description="Extract links from HTML"
    )
    html_extract_images: bool = Field(
        default=True, description="Extract image metadata from HTML"
    )
    html_clean_content: bool = Field(default=True, description="Clean HTML content")
    html_timeout: float = Field(
        default=20.0, description="HTTP timeout in seconds for fetching HTML"
    )
    html_retries: int = Field(
        default=2, description="Number of retries for fetching HTML"
    )
    html_extractor: Literal["simple", "readability"] = Field(
        default="simple", description="Main content extractor strategy"
    )
    html_enable_structural_extraction: bool = Field(
        default=True, description="Enable structural extraction (h1–h6, lists)"
    )
    html_inject_heading_markers: bool = Field(
        default=True, description="Inject Markdown-style heading markers into text"
    )
    html_detect_language: bool = Field(
        default=True, description="Detect language from <html lang> or heuristics"
    )
    html_user_agent: str = Field(
        default="ragbot-html-loader/1.0 (+https://github.com)",
        description="Custom User-Agent for HTTP requests",
    )
    html_user_agent_mode: Literal["fixed", "random", "chrome", "firefox", "auto"] = (
        Field(
            default="fixed",
            description="How to choose User-Agent: fixed|random|chrome|firefox|auto (fake-useragent)",
        )
    )
    html_custom_headers: Optional[str] = Field(
        default=None,
        description="JSON string of extra headers to include in HTTP requests",
    )
    html_cookies: Optional[str] = Field(
        default=None,
        description="Cookie header string 'k=v; k2=v2' to include in HTTP requests",
    )
    html_max_links: int = Field(
        default=200, description="Maximum number of links to record in metadata"
    )
    html_max_images: int = Field(
        default=200, description="Maximum number of images to record in metadata"
    )

    # DOCX settings
    docx_enable_structural_extraction: bool = Field(
        default=True, description="Enable structural extraction in DOCX (headings)"
    )
    docx_inject_heading_markers: bool = Field(
        default=True, description="Inject Markdown-style markers for headings in DOCX"
    )
    docx_extract_hyperlinks: bool = Field(
        default=True, description="Extract hyperlinks from DOCX"
    )
    docx_extract_images: bool = Field(
        default=False, description="Extract image metadata from DOCX"
    )
    docx_detect_language: bool = Field(
        default=True, description="Detect language for DOCX documents"
    )
    docx_hyperlinks_max: int = Field(
        default=200, description="Maximum hyperlinks to record from DOCX"
    )
    docx_images_max: int = Field(
        default=100, description="Maximum images to record from DOCX"
    )
    docx_tables_max: int = Field(
        default=200, description="Maximum tables to process from DOCX"
    )
    docx_preserve_numbering: bool = Field(
        default=True, description="Reconstruct simple numbering/bullets in output text"
    )
    docx_inject_hyperlinks_inline: bool = Field(
        default=False, description="Inject [text](url) inline for extracted hyperlinks"
    )
    docx_paragraph_breaks: int = Field(
        default=1, description="Number of newlines between paragraphs/blocks"
    )
    docx_max_zip_entries: int = Field(
        default=20000, description="Safety cap: maximum allowed entries inside DOCX zip"
    )
    docx_max_uncompressed_mb: int = Field(
        default=512,
        description="Safety cap: max total uncompressed size (MB) of DOCX zip",
    )
    # Heading detection controls
    docx_heading_auto: bool = Field(
        default=True,
        description="Enable automatic multi-signal heading detection (style_id, outlineLvl, font/layout)",
    )
    docx_heading_font_bins: Optional[str] = Field(
        default=None,
        description="Optional JSON list of absolute font pt thresholds for H1..Hn (e.g., [20,16,14])",
    )

    # تنظیمات Markdown
    markdown_extract_code: bool = Field(
        default=True, description="Extract code blocks from Markdown"
    )
    markdown_extract_tables: bool = Field(
        default=True, description="Extract tables from Markdown"
    )
    markdown_detect_language: bool = Field(
        default=False,
        description="Detect language for Markdown content (3-segment voting)",
    )

    model_config = SettingsConfigDict(
        env_prefix="MULTI_FORMAT_",
        extra="ignore",
    )

    # PPTX settings
    pptx_inject_heading_markers: bool = Field(
        default=True, description="Inject Markdown-style markers for headings in PPTX"
    )
    pptx_heading_auto: bool = Field(
        default=True, description="Enable automatic heading detection for PPTX"
    )
    pptx_heading_font_delta: float = Field(
        default=4.0,
        description="Base delta threshold (pt) above body font for H3; H2 uses stronger delta",
    )
    pptx_detect_language: bool = Field(
        default=False, description="Enable language detection for PPTX documents"
    )
    pptx_max_zip_entries: int = Field(
        default=5000, description="Safety cap: maximum allowed entries inside PPTX zip"
    )
    pptx_max_uncompressed_mb: int = Field(
        default=500,
        description="Safety cap: max total uncompressed size (MB) of PPTX zip",
    )
    pptx_hyperlinks_max: int = Field(
        default=100, description="Maximum number of PPTX hyperlinks to record"
    )
    pptx_images_max: int = Field(
        default=200, description="Maximum number of PPTX images to record"
    )
    pptx_inject_hyperlinks_inline: bool = Field(
        default=True, description="Inject paragraph hyperlinks inline into text lines"
    )


class PerformanceSettings(PydanticBaseSettings):
    """تنظیمات بهینه‌سازی عملکرد"""

    # Monitoring
    enable_monitoring: bool = Field(
        default=True,
        description="Enable performance monitoring",
        validation_alias=AliasChoices(
            "enable_monitoring", "enable_performance_monitoring"
        ),
    )

    @property
    def enable_performance_monitoring(self) -> bool:
        return self.enable_monitoring

    @enable_performance_monitoring.setter
    def enable_performance_monitoring(self, value: bool) -> None:
        self.enable_monitoring = value
    monitoring_interval: int = Field(
        default=10, description="Performance monitoring interval in seconds"
    )
    metrics_retention_days: int = Field(
        default=7, description="Metrics retention period in days"
    )

    # Resource monitoring
    enable_resource_monitoring: bool = Field(
        default=True, description="Enable resource monitoring"
    )
    resource_check_interval: int = Field(
        default=5, description="Resource check interval in seconds"
    )
    alert_thresholds: Dict[str, float] = Field(
        default={"cpu": 80.0, "memory": 85.0, "disk": 90.0},
        description="Resource alert thresholds",
    )

    # Optional split env overrides (keep .env_deepseek backward-compatible)
    alert_thresholds_cpu: Optional[float] = Field(
        default=None, description="Override CPU alert threshold via env"
    )
    alert_thresholds_memory: Optional[float] = Field(
        default=None, description="Override Memory alert threshold via env"
    )
    alert_thresholds_disk: Optional[float] = Field(
        default=None, description="Override Disk alert threshold via env"
    )

    # Async processing
    max_async_workers: int = Field(default=4, description="Maximum async workers")
    max_concurrent_tasks: int = Field(
        default=10, description="Maximum concurrent tasks"
    )
    batch_size: int = Field(default=10, description="Default batch size")

    # Memory optimization
    enable_memory_optimization: bool = Field(
        default=True, description="Enable memory optimization"
    )
    max_memory_usage: float = Field(
        default=0.8, description="Maximum memory usage threshold"
    )
    optimization_interval: int = Field(
        default=60, description="Memory optimization interval in seconds"
    )
    gc_threshold: int = Field(default=1000, description="Garbage collection threshold")

    # Performance limits
    max_response_time: float = Field(
        default=5.0, description="Maximum response time in seconds"
    )
    max_throughput: int = Field(
        default=1000, description="Maximum throughput per minute"
    )
    max_concurrent_requests: int = Field(
        default=50, description="Maximum concurrent requests"
    )

    model_config = SettingsConfigDict(
        env_prefix="PERFORMANCE_",
        extra="ignore",
    )

    @field_validator("alert_thresholds", mode="after")
    @classmethod
    def compose_alert_thresholds(cls, v: Dict[str, float], info) -> Dict[str, float]:
        """Compose alert thresholds from split env vars if provided (Pydantic v2)."""
        try:
            data = getattr(info, "data", {}) or {}
        except Exception:
            data = {}
        cpu = data.get("alert_thresholds_cpu")
        mem = data.get("alert_thresholds_memory")
        dsk = data.get("alert_thresholds_disk")

        # Start from existing value and overlay any split overrides
        composed = dict(v or {})
        if cpu is not None:
            composed["cpu"] = float(cpu)
        if mem is not None:
            composed["memory"] = float(mem)
        if dsk is not None:
            composed["disk"] = float(dsk)

        # Fallback to sane defaults if keys missing
        composed.setdefault("cpu", 80.0)
        composed.setdefault("memory", 85.0)
        composed.setdefault("disk", 90.0)
        return composed


class MonitoringSettings(PydanticBaseSettings):
    """Monitoring, health and alerting configuration settings."""

    # Prometheus metrics
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=8080, description="Metrics server port")

    # Health checks
    health_check_interval: int = Field(
        default=30, description="Health check interval in seconds"
    )

    # Real-time monitoring
    enable_real_time_monitoring: bool = Field(
        default=True, description="Enable real-time monitoring"
    )
    monitoring_interval: int = Field(
        default=10, description="Real-time monitoring interval in seconds"
    )
    metrics_retention_hours: int = Field(
        default=24, description="Retention period for in-memory metrics history"
    )

    # Alerting
    enable_alerting: bool = Field(default=True, description="Enable alerting system")
    alert_check_interval: int = Field(default=30, description="Alert check interval")
    alert_cooldown_minutes: int = Field(default=5, description="Alert cooldown minutes")
    alert_thresholds: Dict[str, float] = Field(
        default={
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "disk_usage": 90.0,
            "response_time": 5.0,
            "error_rate": 10.0,
        },
        description="Alert thresholds",
    )
    notification_channels: Dict[str, Dict[str, Any]] = Field(
        default={
            "email": {
                "enabled": False,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "recipients": [],
            },
            "slack": {"enabled": False, "webhook_url": "", "channel": "#alerts"},
        },
        description="Notification channels configuration",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    model_config = SettingsConfigDict(
        env_prefix="MONITORING_",
        extra="ignore",
    )


class UserAnalyticsSettings(PydanticBaseSettings):
    """تنظیمات تحلیل کاربر"""

    # تحلیل رفتار
    enable_user_analytics: bool = Field(
        default=True, description="Enable user analytics"
    )
    track_user_sessions: bool = Field(default=True, description="Track user sessions")
    track_query_patterns: bool = Field(default=True, description="Track query patterns")
    track_document_preferences: bool = Field(
        default=True, description="Track document preferences"
    )

    # رضایت
    enable_satisfaction_tracking: bool = Field(
        default=True, description="Enable satisfaction tracking"
    )
    satisfaction_prompt_frequency: int = Field(
        default=5, description="How often to prompt for satisfaction (every N queries)"
    )
    satisfaction_rating_scale: int = Field(
        default=5, description="Satisfaction rating scale (1-N)"
    )

    # حریم خصوصی
    anonymize_user_data: bool = Field(default=False, description="Anonymize user data")
    data_retention_days: int = Field(
        default=90, description="Data retention period in days"
    )
    export_user_data: bool = Field(default=True, description="Allow user data export")

    # تنظیمات پیشرفته
    session_timeout_hours: int = Field(
        default=1, description="Session timeout in hours"
    )
    max_session_history: int = Field(
        default=1000, description="Maximum session history to keep"
    )
    analytics_update_interval: int = Field(
        default=300, description="Analytics update interval in seconds"
    )

    model_config = SettingsConfigDict(
        env_prefix="ANALYTICS_",
        extra="ignore",
    )


class AdvancedChunkingSettings(PydanticBaseSettings):
    """تنظیمات تقسیم‌بندی پیشرفته"""

    # استراتژی تقسیم‌بندی
    chunking_strategy: str = Field(
        default="adaptive",
        description="Chunking strategy: semantic|hierarchical|hybrid|full|adaptive|token",
    )
    enable_chunk_optimization: bool = Field(
        default=True, description="Enable post-chunk optimization"
    )

    # تنظیمات تقسیم‌بندی معنایی
    semantic_similarity_threshold: float = Field(
        default=0.7, description="Similarity threshold for semantic grouping"
    )
    semantic_min_chunk_size: int = Field(default=100, description="Min chunk chars")
    semantic_max_chunk_size: int = Field(default=1000, description="Max chunk chars")
    semantic_min_sentence_chars: int = Field(
        default=8, description="Minimum characters required for a sentence"
    )

    # تنظیمات تقسیم‌بندی سلسله‌مراتبی
    hierarchical_max_levels: int = Field(default=3, description="Max levels")
    hierarchical_min_chunk_size: int = Field(
        default=100, description="Min paragraph size"
    )
    hierarchical_max_chunk_size: int = Field(
        default=2000, description="Max paragraph size"
    )

    # تنظیمات تقسیم‌بندی تطبیقی
    adaptive_text_length_threshold: int = Field(
        default=5000, description="Text length threshold for hybrid strategy"
    )
    adaptive_structure_complexity_threshold: float = Field(
        default=0.3, description="Structure score threshold for hierarchical"
    )
    adaptive_semantic_coherence_threshold: float = Field(
        default=0.7, description="Semantic score threshold for semantic"
    )

    # تنظیمات بهینه‌ساز
    chunk_target_size: int = Field(default=500, description="Target chunk size")
    chunk_size_tolerance: float = Field(default=0.2, description="Size tolerance ratio")
    enable_chunk_quality_analysis: bool = Field(
        default=True, description="Enable chunk quality analysis"
    )
    # تنظیمات fallback برای TokenChunker (بدون tiktoken)
    token_fallback_density_factor: float = Field(
        default=0.7,
        description="Density factor used to approximate tokens from words in fallback mode",
        ge=0.1,
        le=1.0,
    )
    # آستانه‌های ریزسازی توکنی (اختیاری - اگر None باشد از chunk_target_size استفاده می‌شود)
    hybrid_refine_token_threshold: Optional[int] = Field(
        default=None,
        description="Token threshold to trigger semantic refinement in hybrid mode",
    )
    full_refine_token_threshold: Optional[int] = Field(
        default=None,
        description="Token threshold to trigger semantic refinement in full mode",
    )
    # ادغام زیرچانک‌های خیلی کوتاه بعد از ریزسازی (نسبت به semantic_min_chunk_size)
    merge_short_chunk_ratio: float = Field(
        default=0.5,
        description="Ratio of semantic_min_chunk_size under which adjacent chunks will be merged",
        ge=0.1,
        le=1.0,
    )
    # ضمیمه‌کردن متادیتاهای تحلیل/استراتژی به خروجی چانک‌ها
    attach_analysis_metadata: bool = Field(
        default=True,
        description="Attach analysis and selected_strategy to chunk metadata",
    )

    model_config = SettingsConfigDict(
        env_prefix="ADV_CHUNK_",
        extra="ignore",
    )


class Settings(PydanticBaseSettings):
    """Main application settings."""

    # Telegram Bot (legacy/optional)
    bot_token: Optional[str] = Field(
        default=None, description="Legacy Telegram bot token"
    )
    allow_users: str = Field(default="", description="Comma-separated user IDs")
    admin_users: str = Field(
        default="",
        description="Comma-separated admin user IDs (for /shutdown, /restart, etc.)",
    )

    @property
    def admin_users_list(self) -> List[int]:
        """Parsed admin user IDs. Empty when not set; no one has admin rights."""
        raw = (self.admin_users or "").strip()
        if not raw:
            return []
        out: List[int] = []
        for part in raw.split(","):
            token = part.strip()
            if not token:
                continue
            try:
                out.append(int(token))
            except ValueError:
                continue
        return out

    @property
    def allow_users_list(self) -> List[int]:
        """Parsed allowlist of user IDs as integers.

        Returns empty list when not set; callers can treat empty as "allow all" if desired.
        """
        raw = (self.allow_users or "").strip()
        if not raw:
            return []
        out: List[int] = []
        for part in raw.split(","):
            token = part.strip()
            if not token:
                continue
            try:
                out.append(int(token))
            except ValueError:
                # Ignore invalid entries gracefully
                continue
        return out

    # Language
    default_lang: Literal["fa", "en"] = Field(
        default="fa", description="Default response language"
    )

    # Advanced Retrieval
    advanced_retrieval: AdvancedRetrievalSettings = Field(
        default_factory=AdvancedRetrievalSettings,
        description="Advanced retrieval settings",
    )

    # Retrieve
    retrieve: RetrieveSettings = Field(
        default_factory=RetrieveSettings,
        description="Retrieve settings",
    )

    # Semantic Cache
    semantic_cache: SemanticCacheSettings = Field(
        default_factory=SemanticCacheSettings,
        description="Semantic cache settings",
    )

    # Plugin System
    plugin_directory: str = Field(
        default="plugins", description="Plugin directory path"
    )
    auto_load_plugins: bool = Field(
        default=False, description="Automatically load plugins on startup"
    )
    plugins: PluginSettings = Field(
        default_factory=PluginSettings,
        description="Plugin system settings",
    )

    # Vector Database
    vector_db: Literal["faiss", "chromadb", "qdrant", "weaviate"] = Field(
        default="faiss", description="Vector database type"
    )
    store_path: Path = Field(
        default=Path("./data/vector_store"), description="Vector store path"
    )
    # Store/FAISS settings
    store: StoreSettings = Field(
        default_factory=StoreSettings, description="Vector store (FAISS) settings"
    )

    # Advanced Vector Store Configuration
    vector_store: VectorStoreConfig = Field(
        default_factory=VectorStoreConfig,
        description="Advanced vector store configuration",
    )

    # API Keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(
        default=None, description="Anthropic API key"
    )
    openrouter_api_key: Optional[str] = Field(
        default=None, description="OpenRouter API key"
    )

    # Caching
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")
    enable_redis: bool = Field(default=False, description="Enable Redis caching")

    # Development
    debug: bool = Field(default=False, description="Enable debug mode")
    log_file: Optional[Path] = Field(
        default=Path("./logs/ragbot.log"), description="Log file path"
    )

    # Data directory
    data_dir: Path = Field(default=Path("./data"), description="Data directory path")

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    multi_format: MultiFormatSettings = Field(default_factory=MultiFormatSettings)
    analytics: UserAnalyticsSettings = Field(default_factory=UserAnalyticsSettings)
    advanced_chunking: AdvancedChunkingSettings = Field(
        default_factory=AdvancedChunkingSettings
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env file
    )

    # Convenience properties for backward compatibility
    @property
    def chunk_size(self) -> int:
        """Get chunk size from RAG settings."""
        return self.rag.chunk_size

    @property
    def chunk_overlap(self) -> int:
        """Get chunk overlap from RAG settings."""
        return self.rag.chunk_overlap

    @property
    def embed_model(self) -> str:
        """Get embedding model from embedding settings."""
        return self.embedding.model

    @property
    def llm_model(self) -> str:
        """Get LLM model from LLM settings."""
        return self.llm.model

    @property
    def llm_temperature(self) -> float:
        """Get LLM temperature from LLM settings."""
        return self.llm.temperature

    @property
    def redis_url(self) -> str:
        """Get Redis URL from Redis settings."""
        return self.redis.url

    @field_validator("store_path")
    @classmethod
    def create_store_path(cls, v: Path) -> Path:
        """Create store path if it doesn't exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("log_file")
    @classmethod
    def create_log_path(cls, v: Optional[Path]) -> Optional[Path]:
        """Create log file directory if it doesn't exist."""
        if v:
            v.parent.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("data_dir")
    @classmethod
    def create_data_dir(cls, v: Path) -> Path:
        """Create data directory if it doesn't exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    def validate_api_keys(self) -> None:
        """Validate that required API keys are present."""
        if self.llm.provider == "openai" and not self.openai_api_key:
            raise ValueError("OpenAI API key is required when using OpenAI provider")
        if self.llm.provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "Anthropic API key is required when using Anthropic provider"
            )
        if self.embedding.provider == "openai" and not self.openai_api_key:
            raise ValueError("OpenAI API key is required when using OpenAI embeddings")

    def validate_all_settings(self) -> Dict[str, Any]:
        """
        Perform comprehensive validation of all settings.

        Returns:
            Dict[str, Any]: Validation result with errors, warnings, and info
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": [],
            "components": {},
        }

        # Validate API keys
        try:
            self.validate_api_keys()
            validation_result["components"]["api_keys"] = {"status": "valid"}
        except ValueError as e:
            validation_result["errors"].append(f"API Keys: {str(e)}")
            validation_result["components"]["api_keys"] = {
                "status": "invalid",
                "error": str(e),
            }
            validation_result["valid"] = False

        # Validate bot token (optional for API backend)
        if self.bot_token:
            if not self.bot_token.startswith(("bot", "BOT")) and ":" not in self.bot_token:
                validation_result["warnings"].append("Bot token format may be invalid")
                validation_result["components"]["bot_token"] = {
                    "status": "warning",
                    "message": "Format may be invalid",
                }
            else:
                validation_result["components"]["bot_token"] = {"status": "valid"}

        # Validate paths
        try:
            if not self.store_path.exists():
                self.store_path.mkdir(parents=True, exist_ok=True)
            validation_result["components"]["store_path"] = {
                "status": "valid",
                "path": str(self.store_path),
            }
        except Exception as e:
            validation_result["errors"].append(f"Store path error: {str(e)}")
            validation_result["components"]["store_path"] = {
                "status": "invalid",
                "error": str(e),
            }
            validation_result["valid"] = False

        if self.log_file:
            try:
                if not self.log_file.parent.exists():
                    self.log_file.parent.mkdir(parents=True, exist_ok=True)
                validation_result["components"]["log_file"] = {
                    "status": "valid",
                    "path": str(self.log_file),
                }
            except Exception as e:
                validation_result["warnings"].append(f"Log file path warning: {str(e)}")
                validation_result["components"]["log_file"] = {
                    "status": "warning",
                    "error": str(e),
                }

        # Validate database settings
        try:
            db_validation = self._validate_database_settings()
            validation_result["components"]["database"] = db_validation
            if not db_validation["valid"]:
                validation_result["errors"].extend(db_validation["errors"])
                validation_result["valid"] = False
        except Exception as e:
            validation_result["errors"].append(f"Database validation failed: {str(e)}")
            validation_result["components"]["database"] = {
                "status": "invalid",
                "error": str(e),
            }
            validation_result["valid"] = False

        # Validate Redis settings (if enabled)
        if self.enable_redis:
            try:
                redis_validation = self._validate_redis_settings()
                validation_result["components"]["redis"] = redis_validation
                if not redis_validation["valid"]:
                    validation_result["warnings"].extend(redis_validation["errors"])
            except Exception as e:
                validation_result["warnings"].append(
                    f"Redis validation failed: {str(e)}"
                )
                validation_result["components"]["redis"] = {
                    "status": "warning",
                    "error": str(e),
                }

        # Validate LLM settings
        try:
            llm_validation = self._validate_llm_settings()
            validation_result["components"]["llm"] = llm_validation
            if not llm_validation["valid"]:
                validation_result["errors"].extend(llm_validation["errors"])
                validation_result["valid"] = False
        except Exception as e:
            validation_result["errors"].append(f"LLM validation failed: {str(e)}")
            validation_result["components"]["llm"] = {
                "status": "invalid",
                "error": str(e),
            }
            validation_result["valid"] = False

        # Validate embedding settings
        try:
            embedding_validation = self._validate_embedding_settings()
            validation_result["components"]["embedding"] = embedding_validation
            if not embedding_validation["valid"]:
                validation_result["errors"].extend(embedding_validation["errors"])
                validation_result["valid"] = False
        except Exception as e:
            validation_result["errors"].append(f"Embedding validation failed: {str(e)}")
            validation_result["components"]["embedding"] = {
                "status": "invalid",
                "error": str(e),
            }
            validation_result["valid"] = False

        # Validate RAG settings
        try:
            rag_validation = self._validate_rag_settings()
            validation_result["components"]["rag"] = rag_validation
            if not rag_validation["valid"]:
                validation_result["errors"].extend(rag_validation["errors"])
                validation_result["valid"] = False
        except Exception as e:
            validation_result["errors"].append(f"RAG validation failed: {str(e)}")
            validation_result["components"]["rag"] = {
                "status": "invalid",
                "error": str(e),
            }
            validation_result["valid"] = False

        # Validate security settings
        try:
            security_validation = self._validate_security_settings()
            validation_result["components"]["security"] = security_validation
            if not security_validation["valid"]:
                validation_result["errors"].extend(security_validation["errors"])
                validation_result["valid"] = False
        except Exception as e:
            validation_result["errors"].append(f"Security validation failed: {str(e)}")
            validation_result["components"]["security"] = {
                "status": "invalid",
                "error": str(e),
            }
            validation_result["valid"] = False

        # Validate monitoring settings
        try:
            monitoring_validation = self._validate_monitoring_settings()
            validation_result["components"]["monitoring"] = monitoring_validation
            if not monitoring_validation["valid"]:
                validation_result["warnings"].extend(monitoring_validation["errors"])
        except Exception as e:
            validation_result["warnings"].append(
                f"Monitoring validation failed: {str(e)}"
            )
            validation_result["components"]["monitoring"] = {
                "status": "warning",
                "error": str(e),
            }

        # Validate performance settings
        try:
            performance_validation = self._validate_performance_settings()
            validation_result["components"]["performance"] = performance_validation
            if not performance_validation["valid"]:
                validation_result["warnings"].extend(performance_validation["errors"])
        except Exception as e:
            validation_result["warnings"].append(
                f"Performance validation failed: {str(e)}"
            )
            validation_result["components"]["performance"] = {
                "status": "warning",
                "error": str(e),
            }

        # Add general info
        validation_result["info"].extend(
            [
                f"Default language: {self.default_lang}",
                f"Vector database: {self.vector_db}",
                f"Debug mode: {self.debug}",
                f"Redis enabled: {self.enable_redis}",
                f"Cache TTL: {self.cache_ttl} seconds",
            ]
        )

        return validation_result

    def _validate_database_settings(self) -> Dict[str, Any]:
        """Validate database configuration."""
        result = {"valid": True, "errors": [], "info": [], "status": "valid"}

        try:
            # Basic URL validation
            if not self.database.url:
                result["errors"].append("Database URL is required")
                result["valid"] = False
                result["status"] = "invalid"
            elif not self.database.url.startswith(
                ("sqlite://", "postgresql://", "mysql://")
            ):
                result["errors"].append("Unsupported database URL scheme")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate pool settings
            if self.database.pool_size <= 0:
                result["errors"].append("Database pool size must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            if self.database.max_overflow < 0:
                result["errors"].append("Database max overflow cannot be negative")
                result["valid"] = False
                result["status"] = "invalid"

            result["info"].append(f"Database URL: {self.database.url}")
            result["info"].append(f"Pool size: {self.database.pool_size}")

        except Exception as e:
            result["errors"].append(f"Database validation error: {str(e)}")
            result["valid"] = False
            result["status"] = "invalid"

        return result

    def _validate_redis_settings(self) -> Dict[str, Any]:
        """Validate Redis configuration."""
        result = {"valid": True, "errors": [], "info": [], "status": "valid"}

        try:
            # Basic URL validation
            if not self.redis.url:
                result["errors"].append("Redis URL is required when Redis is enabled")
                result["valid"] = False
                result["status"] = "invalid"
            elif not self.redis.url.startswith("redis://"):
                result["errors"].append("Invalid Redis URL scheme")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate connection settings
            if self.redis.max_connections <= 0:
                result["errors"].append("Redis max connections must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            if self.redis.socket_timeout <= 0:
                result["errors"].append("Redis socket timeout must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            result["info"].append(f"Redis URL: {self.redis.url}")
            result["info"].append(f"Max connections: {self.redis.max_connections}")

        except Exception as e:
            result["errors"].append(f"Redis validation error: {str(e)}")
            result["valid"] = False
            result["status"] = "invalid"

        return result

    def _validate_llm_settings(self) -> Dict[str, Any]:
        """Validate LLM configuration."""
        result = {"valid": True, "errors": [], "info": [], "status": "valid"}

        try:
            # Validate provider
            allowed_providers = [
                "openai",
                "anthropic",
                "ollama",
                "openrouter",
                "hf_local",
            ]
            if self.llm.provider not in allowed_providers:
                result["errors"].append(f"Invalid LLM provider: {self.llm.provider}")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate model name
            if not self.llm.model:
                result["errors"].append("LLM model name is required")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate numeric settings
            if self.llm.max_tokens is not None and self.llm.max_tokens <= 0:
                result["errors"].append(
                    "LLM max tokens must be positive when specified"
                )
                result["valid"] = False
                result["status"] = "invalid"

            if not 0.0 <= self.llm.temperature <= 2.0:
                result["errors"].append("LLM temperature must be between 0.0 and 2.0")
                result["valid"] = False
                result["status"] = "invalid"

            if self.llm.timeout <= 0:
                result["errors"].append("LLM timeout must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            result["info"].append(f"Provider: {self.llm.provider}")
            result["info"].append(f"Model: {self.llm.model}")
            result["info"].append(f"Max tokens: {self.llm.max_tokens}")

        except Exception as e:
            result["errors"].append(f"LLM validation error: {str(e)}")
            result["valid"] = False
            result["status"] = "invalid"

        return result

    def _validate_embedding_settings(self) -> Dict[str, Any]:
        """Validate embedding configuration."""
        result = {"valid": True, "errors": [], "info": [], "status": "valid"}

        try:
            # Validate provider
            allowed_providers = ["openai", "huggingface", "sentence_transformers"]
            if self.embedding.provider not in allowed_providers:
                result["errors"].append(
                    f"Invalid embedding provider: {self.embedding.provider}"
                )
                result["valid"] = False
                result["status"] = "invalid"

            # Validate model name
            if not self.embedding.model:
                result["errors"].append("Embedding model name is required")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate numeric settings
            if self.embedding.batch_size <= 0:
                result["errors"].append("Embedding batch size must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            if self.embedding.timeout <= 0:
                result["errors"].append("Embedding timeout must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            result["info"].append(f"Provider: {self.embedding.provider}")
            result["info"].append(f"Model: {self.embedding.model}")
            result["info"].append(f"Batch size: {self.embedding.batch_size}")

        except Exception as e:
            result["errors"].append(f"Embedding validation error: {str(e)}")
            result["valid"] = False
            result["status"] = "invalid"

        return result

    def _validate_rag_settings(self) -> Dict[str, Any]:
        """Validate RAG configuration."""
        result = {"valid": True, "errors": [], "info": [], "status": "valid"}

        try:
            # Validate chunk settings
            if self.rag.chunk_size <= 0 or self.rag.chunk_size > 2000:
                result["errors"].append("RAG chunk size must be between 1 and 2000")
                result["valid"] = False
                result["status"] = "invalid"

            if (
                self.rag.chunk_overlap < 0
                or self.rag.chunk_overlap >= self.rag.chunk_size
            ):
                result["errors"].append(
                    "RAG chunk overlap must be non-negative and less than chunk size"
                )
                result["valid"] = False
                result["status"] = "invalid"

            # Validate retrieval settings
            if self.rag.top_k <= 0 or self.rag.top_k > 20:
                result["errors"].append("RAG top_k must be between 1 and 20")
                result["valid"] = False
                result["status"] = "invalid"

            if not 0.0 <= self.rag.similarity_threshold <= 1.0:
                result["errors"].append(
                    "RAG similarity threshold must be between 0.0 and 1.0"
                )
                result["valid"] = False
                result["status"] = "invalid"

            if self.rag.max_chunks_per_document <= 0:
                result["errors"].append("RAG max chunks per document must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            result["info"].append(f"Chunk size: {self.rag.chunk_size}")
            result["info"].append(f"Top K: {self.rag.top_k}")
            result["info"].append(
                f"Similarity threshold: {self.rag.similarity_threshold}"
            )

        except Exception as e:
            result["errors"].append(f"RAG validation error: {str(e)}")
            result["valid"] = False
            result["status"] = "invalid"

        return result

    def _validate_security_settings(self) -> Dict[str, Any]:
        """Validate security configuration."""
        result = {"valid": True, "errors": [], "info": [], "status": "valid"}

        try:
            # Validate file size limits
            if self.security.max_file_size_mb <= 0:
                result["errors"].append("Security max file size must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate allowed file types
            if not self.security.allowed_file_types:
                result["errors"].append("Security allowed file types cannot be empty")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate rate limiting
            if self.security.rate_limit_requests <= 0:
                result["errors"].append("Security rate limit requests must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            if self.security.rate_limit_window <= 0:
                result["errors"].append("Security rate limit window must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            result["info"].append(f"Max file size: {self.security.max_file_size_mb}MB")
            result["info"].append(
                f"Allowed file types: {', '.join(self.security.allowed_file_types)}"
            )
            result["info"].append(
                f"Rate limit: {self.security.rate_limit_requests} requests per {self.security.rate_limit_window}s"
            )

        except Exception as e:
            result["errors"].append(f"Security validation error: {str(e)}")
            result["valid"] = False
            result["status"] = "invalid"

        return result

    def _validate_monitoring_settings(self) -> Dict[str, Any]:
        """Validate monitoring configuration."""
        result = {"valid": True, "errors": [], "info": [], "status": "valid"}

        try:
            # Validate metrics port
            if not 1024 <= self.monitoring.metrics_port <= 65535:
                result["errors"].append(
                    "Monitoring metrics port must be between 1024 and 65535"
                )
                result["valid"] = False
                result["status"] = "invalid"

            # Validate health check interval
            if self.monitoring.health_check_interval <= 0:
                result["errors"].append(
                    "Monitoring health check interval must be positive"
                )
                result["valid"] = False
                result["status"] = "invalid"

            # Validate log level
            allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if self.monitoring.log_level not in allowed_levels:
                result["errors"].append(
                    f"Invalid log level: {self.monitoring.log_level}"
                )
                result["valid"] = False
                result["status"] = "invalid"

            result["info"].append(f"Metrics enabled: {self.monitoring.enable_metrics}")
            result["info"].append(f"Log level: {self.monitoring.log_level}")
            result["info"].append(
                f"Health check interval: {self.monitoring.health_check_interval}s"
            )

        except Exception as e:
            result["errors"].append(f"Monitoring validation error: {str(e)}")
            result["valid"] = False
            result["status"] = "invalid"

        return result

    def _validate_performance_settings(self) -> Dict[str, Any]:
        """Validate performance configuration."""
        result = {"valid": True, "errors": [], "info": [], "status": "valid"}

        try:
            # Validate monitoring intervals
            if self.performance.monitoring_interval <= 0:
                result["errors"].append(
                    "Performance monitoring interval must be positive"
                )
                result["valid"] = False
                result["status"] = "invalid"

            if self.performance.resource_check_interval <= 0:
                result["errors"].append("Resource check interval must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate alert thresholds
            for (
                threshold_name,
                threshold_value,
            ) in self.performance.alert_thresholds.items():
                if not 0.0 <= threshold_value <= 100.0:
                    result["errors"].append(
                        f"Alert threshold {threshold_name} must be between 0.0 and 100.0"
                    )
                    result["valid"] = False
                    result["status"] = "invalid"

            # Validate async processing settings
            if self.performance.max_async_workers <= 0:
                result["errors"].append("Max async workers must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            if self.performance.max_concurrent_tasks <= 0:
                result["errors"].append("Max concurrent tasks must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            if self.performance.batch_size <= 0:
                result["errors"].append("Batch size must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate memory optimization settings
            if not 0.0 <= self.performance.max_memory_usage <= 1.0:
                result["errors"].append("Max memory usage must be between 0.0 and 1.0")
                result["valid"] = False
                result["status"] = "invalid"

            if self.performance.optimization_interval <= 0:
                result["errors"].append("Optimization interval must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            # Validate performance limits
            if self.performance.max_response_time <= 0:
                result["errors"].append("Max response time must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            if self.performance.max_throughput <= 0:
                result["errors"].append("Max throughput must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            if self.performance.max_concurrent_requests <= 0:
                result["errors"].append("Max concurrent requests must be positive")
                result["valid"] = False
                result["status"] = "invalid"

            result["info"].append(
                f"Performance monitoring: {self.performance.enable_monitoring}"
            )
            result["info"].append(
                f"Resource monitoring: {self.performance.enable_resource_monitoring}"
            )
            result["info"].append(
                f"Memory optimization: {self.performance.enable_memory_optimization}"
            )
            result["info"].append(
                f"Max async workers: {self.performance.max_async_workers}"
            )

        except Exception as e:
            result["errors"].append(f"Performance validation error: {str(e)}")
            result["valid"] = False
            result["status"] = "invalid"

        return result

    def get_environment_info(self) -> Dict[str, Any]:
        """
        Get information about the current environment configuration.

        Returns:
            Dict[str, Any]: Environment information
        """
        import os
        import platform
        import sys

        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "environment_variables": {
                "BOT_TOKEN": "***" if self.bot_token else "Not set",
                "OPENAI_API_KEY": "***" if self.openai_api_key else "Not set",
                "ANTHROPIC_API_KEY": "***" if self.anthropic_api_key else "Not set",
                "DEBUG": str(self.debug),
                "DEFAULT_LANG": self.default_lang,
                "VECTOR_DB": self.vector_db,
                "ENABLE_REDIS": str(self.enable_redis),
            },
            "paths": {
                "store_path": str(self.store_path),
                "log_file": str(self.log_file) if self.log_file else "Not set",
                "current_directory": os.getcwd(),
            },
            "configuration_sources": {
                "env_file": ".env",
                "environment_variables": True,
                "defaults": True,
            },
        }

    def reload_from_env(self) -> None:
        """
        Reload configuration from environment variables.

        This method re-reads environment variables and updates the settings.
        Useful for runtime configuration updates.
        """
        import os

        from dotenv import load_dotenv

        # Reload .env file
        load_dotenv(override=True)

        # Update settings from environment
        fields_dict = getattr(self, "model_fields", getattr(self, "__fields__", {}))
        for field_name, field in fields_dict.items():
            field_info = getattr(field, "field_info", field)
            extra = getattr(field_info, "extra", {}) or {}
            env_name = extra.get("env", field_name.upper()) if isinstance(extra, dict) else field_name.upper()
            env_value = os.getenv(env_name)

            if env_value is not None:
                # Convert string to appropriate type
                field_type = getattr(field, "annotation", getattr(field, "type_", str))
                try:
                    if field_type == bool:
                        setattr(
                            self,
                            field_name,
                            env_value.lower() in ("true", "1", "yes", "on"),
                        )
                    elif field_type == int:
                        setattr(self, field_name, int(env_value))
                    elif field_type == float:
                        setattr(self, field_name, float(env_value))
                    elif field_type == Path:
                        setattr(self, field_name, Path(env_value))
                    else:
                        setattr(self, field_name, env_value)
                except (ValueError, TypeError) as e:
                    import warnings

                    warnings.warn(
                        f"Failed to reload {field_name} from environment: {e}",
                        stacklevel=2,
                    )

        # Re-validate after reload
        try:
            self.validate_api_keys()
        except ValueError as e:
            import warnings

            warnings.warn(
                f"Configuration warning after reload: {e}", UserWarning, stacklevel=2
            )


# Global settings instance
def _create_settings() -> Settings:
    """Create settings instance with fallback for testing."""
    import os
    from dotenv import load_dotenv

    if os.getenv("TESTING") == "true" and os.path.exists(".env.test"):
        load_dotenv(".env.test", override=True)
    else:
        load_dotenv()
    # Map alternative VECTOR_STORE_* envs to STORE_* keys before instantiation
    try:
        import os

        mappings = {
            # Provider
            "VECTOR_STORE_DEFAULT_STORE": "VECTOR_DB",
            # Chroma
            "VECTOR_STORE_CHROMA_PERSIST_DIRECTORY": "STORE_CHROMA_PERSIST_DIRECTORY",
            "VECTOR_STORE_CHROMA_COLLECTION_NAME": "STORE_CHROMA_COLLECTION_NAME",
            "VECTOR_STORE_CHROMA_DISTANCE_FUNCTION": "STORE_CHROMA_DISTANCE_FUNCTION",
            # Qdrant
            "VECTOR_STORE_QDRANT_URL": "STORE_QDRANT_URL",
            "VECTOR_STORE_QDRANT_PATH": "STORE_QDRANT_PATH",
            "VECTOR_STORE_QDRANT_COLLECTION_NAME": "STORE_QDRANT_COLLECTION_NAME",
            "VECTOR_STORE_QDRANT_VECTOR_SIZE": "STORE_QDRANT_VECTOR_SIZE",
            "VECTOR_STORE_QDRANT_TIMEOUT": "STORE_QDRANT_TIMEOUT",
        }
        for src, dst in mappings.items():
            if os.getenv(src) and not os.getenv(dst):
                os.environ[dst] = os.environ[src]
    except Exception:
        pass
    return Settings()


try:
    settings = _create_settings()
    # Validate API keys on import
    try:
        settings.validate_api_keys()
    except ValueError as e:
        # Log warning but don't fail on import
        import warnings

        warnings.warn(f"Configuration warning: {e}", UserWarning, stacklevel=2)
except Exception as e:
    # Fallback settings for testing
    import warnings

    warnings.warn(
        f"Settings initialization failed: {e}, using minimal settings",
        UserWarning,
        stacklevel=2,
    )
    from dotenv import load_dotenv

    load_dotenv()

    settings = Settings()
