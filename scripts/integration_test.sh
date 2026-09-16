#!/bin/bash

# RAG Telegram Bot Integration Test Script
# Tests complete system integration and validates all components work together

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEST_ENV_FILE=".env.testing"
DOCKER_COMPOSE_TEST="docker-compose.test.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Test result functions
test_passed() {
    ((TESTS_PASSED++))
    log_success "✓ $1"
}

test_failed() {
    ((TESTS_FAILED++))
    FAILED_TESTS+=("$1")
    log_error "✗ $1"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up test environment..."

    # Stop test containers
    if [[ -f "$DOCKER_COMPOSE_TEST" ]]; then
        docker-compose -f "$DOCKER_COMPOSE_TEST" down -v --remove-orphans 2>/dev/null || true
    fi

    # Remove test environment file
    [[ -f "$TEST_ENV_FILE" ]] && rm -f "$TEST_ENV_FILE"

    # Remove test data
    [[ -d "test_data" ]] && rm -rf test_data

    log_info "Cleanup completed"
}

# Set up cleanup trap
trap cleanup EXIT

# Setup test environment
setup_test_environment() {
    log_info "Setting up test environment..."

    cd "$PROJECT_DIR"

    # Create test environment file
    cat > "$TEST_ENV_FILE" << EOF
# Test environment configuration
BOT_TOKEN=test_bot_token_123456789
OPENAI_API_KEY=test_openai_key_sk-123456789
DEFAULT_LANG=fa
LOG_LEVEL=DEBUG
CACHE_TTL=60
CHUNK_SIZE=256
TOP_K=3
VECTOR_DB=faiss
EMBED_MODEL=text-embedding-ada-002
REDIS_URL=redis://redis-test:6379
TESTING=true
EOF

    # Create test docker-compose file
    cat > "$DOCKER_COMPOSE_TEST" << EOF
version: '3.8'

services:
  ragbot-test:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    container_name: ragbot-integration-test
    env_file: $TEST_ENV_FILE
    volumes:
      - ./test_data:/app/data
      - ./test_logs:/app/logs
    depends_on:
      - redis-test
    networks:
      - test-network
    command: ["python", "-c", "import time; time.sleep(30)"]  # Keep container running

  redis-test:
    image: redis:7-alpine
    container_name: ragbot-redis-test
    networks:
      - test-network
    command: redis-server --appendonly no

networks:
  test-network:
    driver: bridge

volumes:
  test-data:
  test-logs:
EOF

    # Create test data directories
    mkdir -p test_data test_logs

    log_success "Test environment setup completed"
}

# Start test services
start_test_services() {
    log_info "Starting test services..."

    # Build and start test containers
    docker-compose -f "$DOCKER_COMPOSE_TEST" up -d --build

    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 10

    # Check if containers are running
    if ! docker-compose -f "$DOCKER_COMPOSE_TEST" ps | grep -q "Up"; then
        test_failed "Test containers failed to start"
        return 1
    fi

    test_passed "Test services started successfully"
}

# Test 1: Configuration validation
test_configuration() {
    log_info "Testing configuration validation..."

    # Test configuration loading
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
from ragbot.configs.settings import Settings
settings = Settings()
print(f'Bot token: {settings.bot_token[:10]}...')
print(f'Default language: {settings.default_lang}')
print('Configuration loaded successfully')
" > /dev/null 2>&1; then
        test_passed "Configuration validation"
    else
        test_failed "Configuration validation"
    fi
}

# Test 2: Database connectivity
test_database_connectivity() {
    log_info "Testing database connectivity..."

    # Test Redis connection
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T redis-test redis-cli ping | grep -q "PONG"; then
        test_passed "Redis connectivity"
    else
        test_failed "Redis connectivity"
    fi

    # Test vector store initialization
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
from ragbot.rag.store.faiss_store import FAISSStore
store = FAISSStore('/app/data/test_index')
print('Vector store initialized successfully')
" > /dev/null 2>&1; then
        test_passed "Vector store initialization"
    else
        test_failed "Vector store initialization"
    fi
}

# Test 3: Document loading and processing
test_document_processing() {
    log_info "Testing document loading and processing..."

    # Create test document
    echo "This is a test document about machine learning and artificial intelligence." > test_data/test_doc.txt

    # Test text loader
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
from ragbot.rag import TextLoader
loader = TextLoader()
docs = loader.load('/app/data/test_doc.txt')
print(f'Loaded {len(docs)} documents')
print(f'Content: {docs[0].content[:50]}...')
" > /dev/null 2>&1; then
        test_passed "Text document loading"
    else
        test_failed "Text document loading"
    fi

    # Test chunking
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
from ragbot.rag import TokenChunker
chunker = TokenChunker(chunk_size=50)
text = 'This is a test document about machine learning and artificial intelligence. It contains multiple sentences for testing chunking functionality.'
chunks = chunker.chunk(text)
print(f'Created {len(chunks)} chunks')
" > /dev/null 2>&1; then
        test_passed "Text chunking"
    else
        test_failed "Text chunking"
    fi
}

# Test 4: Embedding generation (mock)
test_embedding_generation() {
    log_info "Testing embedding generation..."

    # Test mock embedder (since we don't have real API keys)
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
import numpy as np
from ragbot.rag import BaseEmbedder

class MockEmbedder(Embedder):
    async def embed(self, texts):
        return [np.random.rand(1536).tolist() for _ in texts]

embedder = MockEmbedder()
import asyncio
embeddings = asyncio.run(embedder.embed(['test text']))
print(f'Generated {len(embeddings)} embeddings')
print(f'Embedding dimension: {len(embeddings[0])}')
" > /dev/null 2>&1; then
        test_passed "Embedding generation (mock)"
    else
        test_failed "Embedding generation (mock)"
    fi
}

# Test 5: Vector store operations
test_vector_store_operations() {
    log_info "Testing vector store operations..."

    # Test vector store add and search
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
import numpy as np
import asyncio
from ragbot.rag.store.faiss_store import FAISSStore

async def test_vector_store():
    store = FAISSStore('/app/data/test_vector_store')

    # Add test vectors
    vectors = [np.random.rand(128).tolist() for _ in range(5)]
    metadata = [{'content': f'Test document {i}'} for i in range(5)]

    await store.add_vectors(vectors, metadata)
    print('Added vectors to store')

    # Search vectors
    query_vector = np.random.rand(128).tolist()
    results = await store.search(query_vector, k=3)
    print(f'Search returned {len(results)} results')

    return True

asyncio.run(test_vector_store())
" > /dev/null 2>&1; then
        test_passed "Vector store operations"
    else
        test_failed "Vector store operations"
    fi
}

# Test 6: RAG pipeline integration
test_rag_pipeline() {
    log_info "Testing RAG pipeline integration..."

    # Test complete RAG pipeline with mocks
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
import asyncio
import numpy as np
from ragbot.rag import TextLoader, TokenChunker
from ragbot.rag.store.faiss_store import FAISSStore

async def test_rag_pipeline():
    # Create test document
    with open('/app/data/pipeline_test.txt', 'w') as f:
        f.write('This is a comprehensive test document for the RAG pipeline. It contains information about artificial intelligence, machine learning, and natural language processing.')

    # Load document
    loader = TextLoader()
    docs = loader.load('/app/data/pipeline_test.txt')
    print(f'Loaded {len(docs)} documents')

    # Chunk text
    chunker = TokenChunker(chunk_size=50)
    chunks = []
    for doc in docs:
        doc_chunks = chunker.chunk(doc.content)
        chunks.extend(doc_chunks)
    print(f'Created {len(chunks)} chunks')

    # Generate mock embeddings
    embeddings = [np.random.rand(128).tolist() for _ in chunks]
    metadata = [{'content': chunk} for chunk in chunks]

    # Store in vector database
    store = FAISSStore('/app/data/pipeline_vector_store')
    await store.add_vectors(embeddings, metadata)
    print('Stored embeddings in vector database')

    # Test retrieval
    query_embedding = np.random.rand(128).tolist()
    results = await store.search(query_embedding, k=2)
    print(f'Retrieved {len(results)} relevant chunks')

    return True

asyncio.run(test_rag_pipeline())
" > /dev/null 2>&1; then
        test_passed "RAG pipeline integration"
    else
        test_failed "RAG pipeline integration"
    fi
}

# Test 7: Error handling and resilience
test_error_handling() {
    log_info "Testing error handling and resilience..."

    # Test invalid file handling
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
from ragbot.rag import TextLoader, RAGError

loader = TextLoader()
try:
    docs = loader.load('/nonexistent/file.txt')
    print('ERROR: Should have raised exception')
    exit(1)
except (FileNotFoundError, RAGException):
    print('Correctly handled file not found error')
except Exception as e:
    print(f'Unexpected error: {e}')
    exit(1)
" > /dev/null 2>&1; then
        test_passed "Error handling for invalid files"
    else
        test_failed "Error handling for invalid files"
    fi

    # Test graceful degradation
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
from ragbot.services.graceful_degradation import GracefulDegradationService

service = GracefulDegradationService()
print('Graceful degradation service initialized')
" > /dev/null 2>&1; then
        test_passed "Graceful degradation service"
    else
        test_failed "Graceful degradation service"
    fi
}

# Test 8: Performance and memory usage
test_performance() {
    log_info "Testing performance and memory usage..."

    # Test memory usage under load
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
import psutil
import gc

# Get initial memory usage
process = psutil.Process()
initial_memory = process.memory_info().rss / 1024 / 1024  # MB

print(f'Initial memory usage: {initial_memory:.2f} MB')

# Simulate some load
data = []
for i in range(1000):
    data.append('x' * 1000)

current_memory = process.memory_info().rss / 1024 / 1024  # MB
print(f'Memory after load: {current_memory:.2f} MB')

# Clean up
del data
gc.collect()

final_memory = process.memory_info().rss / 1024 / 1024  # MB
print(f'Memory after cleanup: {final_memory:.2f} MB')

# Check if memory usage is reasonable (less than 500MB for test)
if final_memory < 500:
    print('Memory usage is within acceptable limits')
else:
    print('WARNING: High memory usage detected')
    exit(1)
" > /dev/null 2>&1; then
        test_passed "Memory usage test"
    else
        test_failed "Memory usage test"
    fi
}

# Test 9: Multi-language support
test_multilingual_support() {
    log_info "Testing multi-language support..."

    # Test Persian text processing
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
from ragbot.rag import TokenChunker

# Test with Persian text
persian_text = 'این یک متن فارسی برای تست سیستم پردازش متن چندزبانه است. سیستم باید قادر به پردازش صحیح متن فارسی باشد.'
chunker = TokenChunker(chunk_size=20)
chunks = chunker.chunk(persian_text)
print(f'Persian text chunked into {len(chunks)} parts')

# Test with English text
english_text = 'This is an English text for testing multilingual text processing system. The system should handle both Persian and English correctly.'
chunks_en = chunker.chunk(english_text)
print(f'English text chunked into {len(chunks_en)} parts')

print('Multi-language support working correctly')
" > /dev/null 2>&1; then
        test_passed "Multi-language support"
    else
        test_failed "Multi-language support"
    fi
}

# Test 10: Security and validation
test_security() {
    log_info "Testing security and validation..."

    # Test input validation
    if docker-compose -f "$DOCKER_COMPOSE_TEST" exec -T ragbot-test python -c "
import sys
sys.path.append('/app')
from ragbot.configs.validator import ConfigValidator

validator = ConfigValidator()

# Test valid configuration
valid_config = {
    'bot_token': '123456789:ABCdefGHI123jklMNOp456qrstuVWXyz',
    'openai_api_key': 'sk-proj-abc123def456ghi789jkl012mno345pqr',
    'default_lang': 'fa'
}

if validator.validate_config(valid_config):
    print('Valid configuration accepted')
else:
    print('ERROR: Valid configuration rejected')
    exit(1)

# Test invalid configuration
invalid_config = {
    'bot_token': 'invalid_token',
    'openai_api_key': 'invalid_key',
    'default_lang': 'invalid_lang'
}

if not validator.validate_config(invalid_config):
    print('Invalid configuration correctly rejected')
else:
    print('ERROR: Invalid configuration accepted')
    exit(1)

print('Security validation working correctly')
" > /dev/null 2>&1; then
        test_passed "Security and validation"
    else
        test_failed "Security and validation"
    fi
}

# Generate test report
generate_test_report() {
    log_info "Generating test report..."

    local total_tests=$((TESTS_PASSED + TESTS_FAILED))
    local success_rate=0

    if [[ $total_tests -gt 0 ]]; then
        success_rate=$(( (TESTS_PASSED * 100) / total_tests ))
    fi

    echo
    echo "=================================="
    echo "    INTEGRATION TEST REPORT"
    echo "=================================="
    echo "Total Tests: $total_tests"
    echo "Passed: $TESTS_PASSED"
    echo "Failed: $TESTS_FAILED"
    echo "Success Rate: $success_rate%"
    echo

    if [[ $TESTS_FAILED -gt 0 ]]; then
        echo "Failed Tests:"
        for test in "${FAILED_TESTS[@]}"; do
            echo "  - $test"
        done
        echo
    fi

    # Save report to file
    cat > integration_test_report.txt << EOF
Integration Test Report
Generated: $(date)

Total Tests: $total_tests
Passed: $TESTS_PASSED
Failed: $TESTS_FAILED
Success Rate: $success_rate%

$(if [[ $TESTS_FAILED -gt 0 ]]; then
    echo "Failed Tests:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  - $test"
    done
fi)
EOF

    if [[ $TESTS_FAILED -eq 0 ]]; then
        log_success "All integration tests passed! ✨"
        return 0
    else
        log_error "Some integration tests failed. Check the report for details."
        return 1
    fi
}

# Main function
main() {
    log_info "Starting RAG Telegram Bot Integration Tests..."

    # Setup and run tests
    setup_test_environment
    start_test_services

    # Run all tests
    test_configuration
    test_database_connectivity
    test_document_processing
    test_embedding_generation
    test_vector_store_operations
    test_rag_pipeline
    test_error_handling
    test_performance
    test_multilingual_support
    test_security

    # Generate report and exit with appropriate code
    generate_test_report
}

# Run main function
main "$@"
