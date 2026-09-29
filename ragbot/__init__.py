"""
TenantRAG

Multi-Tenant Retrieval-Augmented Generation (RAG) Microservice
for SaaS Backends.
"""

__version__ = "1.0.0"
__author__ = "TenantRAG Contributors"

# Core RAG components
from ragbot.rag import (
    AdvancedFilter,
    BaseVectorStore,
    CustomScorer,
    # Query features
    QueryAggregator,
    QueryOptimizer,
    VectorDocument,
    # Store components
    VectorStoreFactory,
)

# Security components
from ragbot.security import EncryptionManager, KeyManager, SecureBackupManager

__all__ = [
    "AdvancedFilter",
    "BaseVectorStore",
    "CustomScorer",
    # Security components
    "EncryptionManager",
    "KeyManager",
    # Query features
    "QueryAggregator",
    "QueryOptimizer",
    "SecureBackupManager",
    "VectorDocument",
    # Store components
    "VectorStoreFactory",
    "__author__",
    "__email__",
    # Version info
    "__version__",
]
