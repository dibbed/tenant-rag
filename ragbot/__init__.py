"""
TenantRAG

Multi-Tenant Retrieval-Augmented Generation (RAG) Microservice
for SaaS Backends.
"""

__version__ = "1.0.0"
__author__ = "TenantRAG Contributors"

# Core RAG components
from ragbot.rag import (
    # Query features
    QueryAggregator,
    AdvancedFilter,
    CustomScorer,
    QueryOptimizer,
    # Store components
    VectorStoreFactory,
    BaseVectorStore,
    VectorDocument,
)

# Security components
from ragbot.security import EncryptionManager, KeyManager, SecureBackupManager

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    # Query features
    "QueryAggregator",
    "AdvancedFilter",
    "CustomScorer",
    "QueryOptimizer",
    # Store components
    "VectorStoreFactory",
    "BaseVectorStore",
    "VectorDocument",
    # Security components
    "EncryptionManager",
    "KeyManager",
    "SecureBackupManager",
]
