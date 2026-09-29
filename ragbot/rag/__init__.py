"""RAG (Retrieval-Augmented Generation) core components"""

# Core components
from .chunkers import (
    AdaptiveChunker,
    BaseChunker,
    HierarchicalChunker,
    SemanticChunker,
    TokenChunker,
)
from .embeddings import BaseEmbedder, HuggingFaceEmbedder, OpenAIEmbedder, STEmbedder

# Exception handling
from .exceptions import (
    DocumentProcessingError,
    EmbeddingError,
    RAGError,
    VectorStoreError,
)
from .loaders import BaseLoader, Document, DOCXLoader, PDFLoader, TextLoader, URLLoader
from .qa import PromptBuilder, PromptTemplate, QAChain
from .query import (
    AdvancedFilter,
    AggregationQuery,
    AggregationResult,
    AggregationType,
    CompositeFilter,
    CustomScorer,
    FilterCondition,
    FilterOperator,
    GeoFilter,
    OptimizationResult,
    OptimizationStrategy,
    QueryAggregator,
    QueryOptimizer,
    QueryPlan,
    ScoredDocument,
    ScoringStrategy,
)
from .retrieve import AdvancedRetriever, DocumentRetriever, HybridRetriever
from .store import BaseVectorStore, SearchResult, VectorDocument, VectorStoreFactory

# Security components - import separately when needed
# from ragbot.security import EncryptionManager, KeyManager, SecureBackupManager

__all__ = [
    "AdaptiveChunker",
    "AdvancedFilter",
    "AdvancedRetriever",
    "AggregationQuery",
    "AggregationResult",
    "AggregationType",
    # Base classes
    "BaseChunker",
    "BaseEmbedder",
    "BaseLoader",
    "BaseVectorStore",
    "CompositeFilter",
    "CustomScorer",
    "DOCXLoader",
    # Data models
    "Document",
    "DocumentProcessingError",
    # Retrieval
    "DocumentRetriever",
    "EmbeddingError",
    "FilterCondition",
    "FilterOperator",
    "GeoFilter",
    "HierarchicalChunker",
    "HuggingFaceEmbedder",
    "HybridRetriever",
    # Embedders
    "OpenAIEmbedder",
    "OptimizationResult",
    "OptimizationStrategy",
    "PDFLoader",
    "PromptBuilder",
    "PromptTemplate",
    # QA
    "QAChain",
    # Query Features
    "QueryAggregator",
    "QueryOptimizer",
    "QueryPlan",
    # Exceptions
    "RAGError",
    "STEmbedder",
    "ScoredDocument",
    "ScoringStrategy",
    "SearchResult",
    "SemanticChunker",
    # Loaders
    "TextLoader",
    # Chunkers
    "TokenChunker",
    "URLLoader",
    "VectorDocument",
    "VectorStoreError",
    # Vector Store
    "VectorStoreFactory",
]
