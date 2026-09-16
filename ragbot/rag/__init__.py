"""RAG (Retrieval-Augmented Generation) core components"""

# Core components
from .chunkers import (
    BaseChunker,
    TokenChunker,
    SemanticChunker,
    HierarchicalChunker,
    AdaptiveChunker,
)
from .embeddings import BaseEmbedder, OpenAIEmbedder, HuggingFaceEmbedder, STEmbedder
from .loaders import BaseLoader, Document, TextLoader, PDFLoader, URLLoader, DOCXLoader
from .qa import QAChain, PromptBuilder
from .retrieve import DocumentRetriever, AdvancedRetriever, HybridRetriever
from .store import BaseVectorStore, VectorDocument, SearchResult, VectorStoreFactory
from .query import (
    QueryAggregator,
    AggregationType,
    AggregationQuery,
    AggregationResult,
    AdvancedFilter,
    FilterOperator,
    FilterCondition,
    CompositeFilter,
    GeoFilter,
    CustomScorer,
    ScoringStrategy,
    ScoredDocument,
    QueryOptimizer,
    OptimizationStrategy,
    QueryPlan,
    OptimizationResult,
)

# Exception handling
from .exceptions import (
    RAGError,
    DocumentProcessingError,
    EmbeddingError,
    VectorStoreError,
)

# Security components - import separately when needed
# from ragbot.security import EncryptionManager, KeyManager, SecureBackupManager

__all__ = [
    # Base classes
    "BaseChunker",
    "BaseEmbedder",
    "BaseLoader",
    "BaseVectorStore",
    # Data models
    "Document",
    "VectorDocument",
    "SearchResult",
    # Chunkers
    "TokenChunker",
    "SemanticChunker",
    "HierarchicalChunker",
    "AdaptiveChunker",
    # Embedders
    "OpenAIEmbedder",
    "HuggingFaceEmbedder",
    "STEmbedder",
    # Loaders
    "TextLoader",
    "PDFLoader",
    "URLLoader",
    "DOCXLoader",
    # QA
    "QAChain",
    "PromptBuilder",
    # Retrieval
    "DocumentRetriever",
    "AdvancedRetriever",
    "HybridRetriever",
    # Vector Store
    "VectorStoreFactory",
    # Query Features
    "QueryAggregator",
    "AggregationType",
    "AggregationQuery",
    "AggregationResult",
    "AdvancedFilter",
    "FilterOperator",
    "FilterCondition",
    "CompositeFilter",
    "GeoFilter",
    "CustomScorer",
    "ScoringStrategy",
    "ScoredDocument",
    "QueryOptimizer",
    "OptimizationStrategy",
    "QueryPlan",
    "OptimizationResult",
    # Exceptions
    "RAGError",
    "DocumentProcessingError",
    "EmbeddingError",
    "VectorStoreError",
]
