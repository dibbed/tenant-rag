"""Text chunking components"""

from .base import BaseChunker, TextChunker
from .chunk_optimizer import ChunkOptimizer
from .hierarchical_chunker import HierarchicalChunker
from .token_chunker import TokenChunker
from .adaptive_chunker import AdaptiveChunker

# Optional semantic chunker import
try:
    from .semantic_chunker import SemanticChunker

    SEMANTIC_CHUNKER_AVAILABLE = True
except ImportError:
    SemanticChunker = None
    SEMANTIC_CHUNKER_AVAILABLE = False

__all__ = [
    "BaseChunker",
    "TextChunker",
    "TokenChunker",
    "ChunkOptimizer",
    "HierarchicalChunker",
    "AdaptiveChunker",
]

if SEMANTIC_CHUNKER_AVAILABLE:
    __all__.append("SemanticChunker")

# Strategy map for convenience
STRATEGY_MAP = {
    "token": TokenChunker,
    "hierarchical": HierarchicalChunker,
    "adaptive": AdaptiveChunker,
}
if SEMANTIC_CHUNKER_AVAILABLE:
    STRATEGY_MAP["semantic"] = SemanticChunker
