"""Text chunking components"""

from .adaptive_chunker import AdaptiveChunker
from .base import BaseChunker, TextChunker
from .chunk_optimizer import ChunkOptimizer
from .hierarchical_chunker import HierarchicalChunker
from .token_chunker import TokenChunker


def _load_semantic_chunker() -> tuple[type[BaseChunker] | None, bool]:
    """Load the optional semantic chunker without conflating a type with None."""
    try:
        from .semantic_chunker import SemanticChunker as semantic_chunker_cls
    except ImportError:
        return None, False
    return semantic_chunker_cls, True


SemanticChunker, SEMANTIC_CHUNKER_AVAILABLE = _load_semantic_chunker()

__all__ = [
    "AdaptiveChunker",
    "BaseChunker",
    "ChunkOptimizer",
    "HierarchicalChunker",
    "TextChunker",
    "TokenChunker",
]

if SEMANTIC_CHUNKER_AVAILABLE:
    __all__.append("SemanticChunker")

# Strategy map for convenience
STRATEGY_MAP: dict[str, type[BaseChunker]] = {
    "token": TokenChunker,
    "hierarchical": HierarchicalChunker,
    "adaptive": AdaptiveChunker,
}
if SemanticChunker is not None:
    STRATEGY_MAP["semantic"] = SemanticChunker
