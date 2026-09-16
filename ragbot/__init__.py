"""
RAG Telegram Assistant

A production-ready Telegram bot using Retrieval-Augmented Generation (RAG)
for providing grounded answers based on ingested documents.
"""

__version__ = "1.0.0"
__author__ = "RAG Bot Team"
__email__ = "support@ragbot.dev"

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
