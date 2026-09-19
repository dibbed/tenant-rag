"""
Shared fixtures and configuration for RAG Telegram bot tests.

This module provides common test fixtures, mock objects, and configuration
that can be used across all test modules.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test environment and enforce GPU safety (CPU only to avoid driver crashes/TDR)
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["TORCH_DEVICE"] = "cpu"
os.environ["TESTING"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENABLE_REDIS"] = "false"


@pytest.fixture(scope="session")
def event_loop_policy():
    """Provide an event loop policy compatible with Windows/Py3.12.

    Do not override the built-in event_loop fixture (pytest-asyncio recommendation).
    """
    if sys.platform.startswith("win"):
        # Prefer selector policy for test stability on Windows
        try:
            return asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined]
        except Exception:
            return asyncio.DefaultEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_text():
    """Sample text for testing."""
    return """
    This is a sample document for testing the RAG system.
    It contains multiple sentences and paragraphs to test text processing.

    The document discusses various topics including artificial intelligence,
    machine learning, and natural language processing. These technologies
    are becoming increasingly important in modern applications.

    RAG (Retrieval-Augmented Generation) combines the power of information
    retrieval with language generation to provide accurate and contextual responses.
    """


@pytest.fixture
def sample_chunks():
    """Sample text chunks for testing."""
    return [
        "This is a sample document for testing the RAG system.",
        "It contains multiple sentences and paragraphs to test text processing.",
        "The document discusses various topics including artificial intelligence.",
        "RAG combines information retrieval with language generation.",
    ]


@pytest.fixture
def sample_embeddings():
    """Sample embeddings for testing."""
    return [
        [0.1, 0.2, 0.3, 0.4, 0.5] * 307 + [0.1, 0.2],  # 1537 dimensions
        [0.2, 0.3, 0.4, 0.5, 0.6] * 307 + [0.2, 0.3],
        [0.3, 0.4, 0.5, 0.6, 0.7] * 307 + [0.3, 0.4],
        [0.4, 0.5, 0.6, 0.7, 0.8] * 307 + [0.4, 0.5],
    ]


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    return [
        {"id": 0, "source": "test_doc.txt", "chunk_index": 0},
        {"id": 1, "source": "test_doc.txt", "chunk_index": 1},
        {"id": 2, "source": "test_doc.txt", "chunk_index": 2},
        {"id": 3, "source": "test_doc.txt", "chunk_index": 3},
    ]


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""

    class MockEmbeddingData:
        def __init__(self, embedding):
            self.embedding = embedding

    class MockUsage:
        def __init__(self):
            self.total_tokens = 100

    class MockResponse:
        def __init__(self, embeddings):
            self.data = [MockEmbeddingData(emb) for emb in embeddings]
            self.usage = MockUsage()

    return MockResponse


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch("ragbot.rag.embeddings.openai_embedder.AsyncOpenAI") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    with patch("redis.asyncio.Redis") as mock_redis:
        mock_instance = AsyncMock()
        mock_redis.return_value = mock_instance

        # Mock common Redis operations
        mock_instance.get.return_value = None
        mock_instance.set.return_value = True
        mock_instance.setex.return_value = True
        mock_instance.delete.return_value = 1
        mock_instance.exists.return_value = 0
        mock_instance.ttl.return_value = -2
        mock_instance.ping.return_value = True
        mock_instance.flushdb.return_value = True
        mock_instance.mget.return_value = []
        mock_instance.info.return_value = {
            "redis_version": "6.0.0",
            "used_memory": 1000000,
            "used_memory_human": "1MB",
            "connected_clients": 1,
            "total_commands_processed": 100,
            "keyspace_hits": 50,
            "keyspace_misses": 25,
        }

        yield mock_instance


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for testing."""
    with patch("aiogram.Bot") as mock_bot:
        mock_instance = AsyncMock()
        mock_bot.return_value = mock_instance

        # Mock common bot operations
        mock_instance.get_me.return_value = MagicMock(username="test_bot")
        mock_instance.send_message.return_value = MagicMock(message_id=123)
        mock_instance.download.return_value = AsyncMock()
        mock_instance.get_file.return_value = MagicMock(file_path="test/path")
        mock_instance.download_file.return_value = AsyncMock()

        yield mock_instance


@pytest.fixture
def mock_faiss_index():
    """Mock FAISS index for testing."""
    with patch("faiss.IndexFlatIP") as mock_index:
        mock_instance = MagicMock()
        mock_index.return_value = mock_instance

        # Mock FAISS operations
        mock_instance.ntotal = 0
        mock_instance.d = 1536
        mock_instance.add = MagicMock()
        mock_instance.search = MagicMock(return_value=([0.9, 0.8, 0.7], [0, 1, 2]))
        mock_instance.reset = MagicMock()

        yield mock_instance


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from ragbot.configs.settings import Settings

    with patch("ragbot.configs.settings.settings") as mock_settings:
        # Create a test settings instance
        test_settings = Settings(
            bot_token="test_token",
            openai_api_key="test_openai_key",
            default_lang="en",
            vector_db="faiss",
            store_path=Path("./test_data/vector_store"),
            debug=True,
            enable_redis=False,
        )

        mock_settings.return_value = test_settings
        yield test_settings


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000206 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n299\n%%EOF"


@pytest.fixture
def sample_search_results():
    """Provide a list of simple search results used by retriever tests."""
    return [
        SimpleNamespace(content="High relevance", metadata={"id": 1}, score=0.95),
        SimpleNamespace(content="Medium relevance", metadata={"id": 2}, score=0.80),
        SimpleNamespace(content="Low relevance", metadata={"id": 3}, score=0.65),
    ]


@pytest.fixture
def sample_url_content():
    """Sample URL content for testing."""
    return """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Test Article</h1>
        <p>This is a test article for URL loading.</p>
        <p>It contains multiple paragraphs with useful information.</p>
        <div>Some additional content in a div.</div>
    </body>
    </html>
    """


@pytest.fixture
def mock_http_response():
    """Mock HTTP response for URL testing."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Test Article</h1>
            <p>This is a test article for URL loading.</p>
            <p>It contains multiple paragraphs with useful information.</p>
        </body>
        </html>
        """
        mock_response.headers = {"content-type": "text/html"}

        mock_get.return_value.__aenter__.return_value = mock_response
        yield mock_response


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    with patch("ragbot.outputs.logger.logger") as mock_logger:
        yield mock_logger


@pytest.fixture
def mock_metrics():
    """Mock metrics manager for testing."""
    with patch("ragbot.outputs.metrics.metrics_manager") as mock_metrics:
        yield mock_metrics


@pytest.fixture
def test_document():
    """Create a test document object."""
    from ragbot.rag.loaders.base import Document

    return Document(
        content="This is a test document content.",
        metadata={"source": "test.txt", "type": "text"},
        source="test.txt",
        document_type="text",
    )


@pytest.fixture
def test_chunks():
    """Create test chunk objects."""
    from ragbot.rag.chunkers.base import TextChunk

    return [
        TextChunk(
            content="This is the first chunk.",
            metadata={"chunk_index": 0, "source": "test.txt"},
            start_index=0,
            end_index=25,
        ),
        TextChunk(
            content="This is the second chunk.",
            metadata={"chunk_index": 1, "source": "test.txt"},
            start_index=26,
            end_index=51,
        ),
    ]


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager for testing."""
    with patch("ragbot.caching.cache_manager") as mock_cache:
        mock_cache.get_cached_embedding.return_value = None
        mock_cache.cache_embedding.return_value = True
        mock_cache.get_cached_query_result.return_value = None
        mock_cache.cache_query_result.return_value = True
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.delete.return_value = True
        mock_cache.clear.return_value = True
        yield mock_cache


@pytest.fixture
def mock_graceful_degradation():
    """Mock graceful degradation service for testing."""
    with patch("ragbot.services.graceful_degradation.graceful_degradation") as mock_gd:
        mock_gd.execute_with_fallback = AsyncMock(
            side_effect=lambda service, func, *args, **kwargs: func(*args, **kwargs)
        )
        mock_gd.get_service_health.return_value = MagicMock(fallback_active=False)
        yield mock_gd


# Test data generators
def generate_test_embeddings(count: int, dimension: int = 1536) -> List[List[float]]:
    """Generate test embeddings."""
    import random

    return [[random.random() for _ in range(dimension)] for _ in range(count)]


def generate_test_chunks(count: int, base_text: str = "Test chunk") -> List[str]:
    """Generate test text chunks."""
    return [f"{base_text} {i}" for i in range(count)]


def generate_test_metadata(
    count: int, source: str = "test.txt"
) -> List[Dict[str, Any]]:
    """Generate test metadata."""
    return [{"id": i, "source": source, "chunk_index": i} for i in range(count)]


@pytest.fixture
def tmp_workspace():
    """Create temporary workspace with cleanup."""
    import shutil
    import tempfile

    d = tempfile.mkdtemp(prefix="ragtest_")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fake_config(tmp_workspace):
    """Standardized test configuration."""
    from types import SimpleNamespace

    return SimpleNamespace(
        vector_db="faiss",
        store_path=str(tmp_workspace / "index"),
        chunk_size=256,
        top_k=4,
        default_lang="fa",
    )


@pytest.fixture
def deterministic_embeddings():
    """Fixed embedding vectors for consistency."""
    return {
        "hello world": [0.1] * 768,
        "salam donya": [0.2] * 768,
        "machine learning": [0.3] * 768,
        "artificial intelligence": [0.4] * 768,
    }


# Async test utilities
async def async_mock_return(value):
    """Helper for async mock returns."""
    return value


def make_async_mock(return_value=None, side_effect=None):
    """Create an async mock with return value or side effect."""
    mock = AsyncMock()
    if return_value is not None:
        mock.return_value = return_value
    if side_effect is not None:
        mock.side_effect = side_effect
    return mock


# Ensure project root is importable as a package for tests
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
