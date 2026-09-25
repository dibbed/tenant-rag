# 🗄️ Vector Store Configuration Guide

## 📋 Overview

RAGBot supports multiple vector databases for different use cases, offering flexibility, scalability, and feature-rich vector storage options while maintaining backward compatibility and ease of use.

## 🎯 Supported Vector Stores

### 1. **FAISS** (Default) ✅

- **Best for**: Fast local development, small to medium datasets
- **Strengths**: Speed, low memory usage, offline operation
- **Configuration**: `VECTOR_STORE_DEFAULT_STORE=faiss`
- **Dependencies**: `faiss-cpu`, `numpy`

#### FAISS Features:

- ✅ Fast similarity search
- ✅ Multiple index types (Flat, IVF, HNSW)
- ✅ GPU support available
- ✅ Offline operation
- ❌ Limited metadata filtering
- ❌ No built-in hybrid search

### 2. **Chroma** 🌟

- **Best for**: RAG applications, metadata-rich data
- **Strengths**: Metadata filtering, easy setup, built-in embedding support
- **Configuration**: `VECTOR_STORE_DEFAULT_STORE=chroma`
- **Dependencies**: `chromadb`

#### Chroma Features:

- ✅ Rich metadata filtering
- ✅ Easy setup and configuration
- ✅ Built-in embedding support
- ✅ Hybrid search capabilities
- ✅ Collection management
- ✅ Persistence out-of-the-box

### 3. **Qdrant** 🚀

- **Best for**: Large datasets, production environments
- **Strengths**: High performance, clustering, REST API
- **Configuration**: `VECTOR_STORE_DEFAULT_STORE=qdrant`
- **Dependencies**: `qdrant-client`

#### Qdrant Features:

- ✅ High performance at scale
- ✅ Advanced payload indexing
- ✅ HNSW algorithm optimization
- ✅ REST API access
- ✅ Clustering support
- ✅ Distributed clustering and replication

## 🔧 Configuration

### Environment Variables

#### Basic Configuration

```bash
# Choose your vector store
VECTOR_STORE_DEFAULT_STORE=faiss  # faiss, chroma, qdrant

# Available stores
VECTOR_STORE_AVAILABLE_STORES=faiss,chroma,qdrant

# Advanced features
VECTOR_STORE_ENABLE_METADATA_FILTERING=true
VECTOR_STORE_ENABLE_SEMANTIC_CHUNKING=true
VECTOR_STORE_ENABLE_HYBRID_SEARCH=true
VECTOR_STORE_ENABLE_RERANKING=true
```

#### FAISS Configuration

```bash
# FAISS Advanced Settings
VECTOR_STORE_FAISS_INDEX_TYPE=flat        # flat, ivf, hnsw
VECTOR_STORE_FAISS_SIMILARITY_METRIC=cosine
VECTOR_STORE_FAISS_NLIST=100
VECTOR_STORE_FAISS_NPROBE=10
VECTOR_STORE_FAISS_HNSW_M=16
VECTOR_STORE_FAISS_HNSW_EF_CONSTRUCTION=200
VECTOR_STORE_FAISS_HNSW_EF_SEARCH=50
VECTOR_STORE_FAISS_ENABLE_GPU=false
VECTOR_STORE_FAISS_GPU_ID=0
```

#### Chroma Configuration

```bash
# Chroma Advanced Settings
VECTOR_STORE_CHROMA_PERSIST_DIRECTORY=./chroma_db
VECTOR_STORE_CHROMA_COLLECTION_NAME=ragbot
VECTOR_STORE_CHROMA_DISTANCE_FUNCTION=cosine
VECTOR_STORE_CHROMA_HNSW_SPACE=cosine
VECTOR_STORE_CHROMA_HNSW_CONSTRUCTION_EF=200
VECTOR_STORE_CHROMA_HNSW_SEARCH_EF=50
VECTOR_STORE_CHROMA_HNSW_M=16
VECTOR_STORE_CHROMA_ENABLE_METADATA_FILTERING=true
VECTOR_STORE_CHROMA_ENABLE_HYBRID_SEARCH=true
VECTOR_STORE_CHROMA_ENABLE_RERANKING=true
```

#### Qdrant Configuration

```bash
# Qdrant Advanced Settings
VECTOR_STORE_QDRANT_URL=http://localhost:6333
VECTOR_STORE_QDRANT_COLLECTION_NAME=ragbot
VECTOR_STORE_QDRANT_VECTOR_SIZE=1536
VECTOR_STORE_QDRANT_TIMEOUT=30
VECTOR_STORE_QDRANT_ENABLE_PAYLOAD_INDEXING=true
VECTOR_STORE_QDRANT_ENABLE_HNSW_INDEX=true
VECTOR_STORE_QDRANT_HNSW_M=16
VECTOR_STORE_QDRANT_HNSW_EF_CONSTRUCTION=200
VECTOR_STORE_QDRANT_HNSW_EF_SEARCH=50
VECTOR_STORE_QDRANT_ENABLE_METADATA_FILTERING=true
VECTOR_STORE_QDRANT_ENABLE_HYBRID_SEARCH=true
VECTOR_STORE_QDRANT_ENABLE_RERANKING=true
```

## 🚀 Quick Start

### Switching Vector Stores

#### Method 1: Environment Variables

```bash
# Switch to Chroma
export VECTOR_STORE_DEFAULT_STORE=chroma

# Switch to Qdrant
export VECTOR_STORE_DEFAULT_STORE=qdrant

# Run the API server
python main.py
```

#### Method 2: Configuration File

```python
# In your .env file
VECTOR_STORE_DEFAULT_STORE=chroma
VECTOR_STORE_CHROMA_PERSIST_DIRECTORY=./chroma_db
```

### Installation

#### Install All Vector Store Dependencies

```bash
# Install all vector store clients
pip install -e ".[vectorstores]"
```

#### Install Individual Stores

```bash
# FAISS (included by default)
pip install faiss-cpu

# Chroma
pip install chromadb

# Qdrant
pip install qdrant-client
```

## 📊 Performance Comparison

| Store    | Search Time (ms) | Memory Usage (MB) | Setup Time (s) | Best For              |
| -------- | ---------------- | ----------------- | -------------- | --------------------- |
| FAISS    | 10-50            | 50-200            | 0.1            | Small-medium datasets |
| Chroma   | 50-200           | 100-500           | 1-5            | RAG applications      |
| Qdrant   | 20-100           | 200-1000          | 5-10           | Large datasets        |

## 🔄 Migration Between Stores

### Basic Migration

```bash
# Migrate from FAISS to Chroma
python -m ragbot.cli migrate-store --source faiss --target chroma

# Migrate from Chroma to Qdrant
python -m ragbot.cli migrate-store --source chroma --target qdrant
```

### Advanced Migration Options

```bash
# Migration with custom settings
python -m ragbot.cli migrate-store \
  --source faiss \
  --target chroma \
  --batch-size 200 \
  --report migration_report.json \
  --no-backup  # Skip backup creation
```

### Migration Features

- ✅ **Batch Processing**: Efficient handling of large datasets
- ✅ **Progress Tracking**: Real-time migration progress
- ✅ **Data Validation**: Verify migrated data integrity
- ✅ **Error Recovery**: Handle and report failed documents
- ✅ **Backup Creation**: Automatic backup before migration
- ✅ **Resume Support**: Continue interrupted migrations

## 📈 Benchmarking

### Run Performance Benchmarks

```bash
# Benchmark all stores
python -m ragbot.cli benchmark-stores

# Benchmark specific stores
python -m ragbot.cli benchmark-stores --stores faiss chroma qdrant

# Custom benchmark parameters
python -m ragbot.cli benchmark-stores \
  --documents 5000 \
  --dimension 1536 \
  --output benchmark_results.json \
  --report benchmark_report.txt
```

### Benchmark Metrics

- **Search Performance**: Average, min, max search times
- **Throughput**: Documents per second for indexing
- **Memory Usage**: RAM consumption during operations
- **Setup Time**: Time to initialize the store
- **Feature Support**: Metadata filtering, hybrid search, etc.

## 🎯 Choosing the Right Store

### Decision Matrix

| Use Case              | Recommended Store | Reason                        |
| --------------------- | ----------------- | ----------------------------- |
| Development/Testing   | FAISS             | Fast, simple, offline         |
| RAG Applications      | Chroma            | Rich metadata, easy setup     |
| Production/Large Data | Qdrant            | High performance, scalable    |
| Prototype/MVP         | FAISS or Chroma   | Quick setup, good performance |
| High Throughput       | Qdrant            | Optimized for performance     |

### Feature Comparison

| Feature            | FAISS | Chroma | Qdrant |
| ------------------ | ----- | ------ | ------ |
| Metadata Filtering | ❌    | ✅     | ✅     |
| Hybrid Search      | ❌    | ✅     | ✅     |
| Reranking          | ❌    | ✅     | ✅     |
| GPU Support        | ✅    | ❌     | ❌     |
| Persistence        | ✅    | ✅     | ✅     |
| Clustering         | ❌    | ❌     | ✅     |
| REST API           | ❌    | ✅     | ✅     |

## 🔧 Advanced Configuration

### Chunking Strategies

```bash
# Semantic chunking (recommended)
VECTOR_STORE_CHUNKING_STRATEGY=semantic
VECTOR_STORE_SEMANTIC_CHUNKING_MODEL=all-MiniLM-L6-v2
VECTOR_STORE_SEMANTIC_CHUNKING_THRESHOLD=0.7

# Token-based chunking
VECTOR_STORE_CHUNKING_STRATEGY=token
VECTOR_STORE_TOKEN_CHUNKING_MAX_TOKENS=512
VECTOR_STORE_TOKEN_CHUNKING_OVERLAP=50

# Hierarchical chunking
VECTOR_STORE_CHUNKING_STRATEGY=hierarchical
VECTOR_STORE_HIERARCHICAL_CHUNKING_MAX_CHUNK_SIZE=512
VECTOR_STORE_HIERARCHICAL_CHUNKING_MIN_CHUNK_SIZE=100
```

### Embedding Configuration

```bash
# Sentence Transformers (default)
VECTOR_STORE_EMBEDDING_PROVIDER=sentence_transformers
VECTOR_STORE_EMBEDDING_MODEL=all-MiniLM-L6-v2
VECTOR_STORE_EMBEDDING_DIMENSION=384

# OpenAI Embeddings
VECTOR_STORE_EMBEDDING_PROVIDER=openai
VECTOR_STORE_OPENAI_EMBEDDING_MODEL=text-embedding-3-small
VECTOR_STORE_OPENAI_EMBEDDING_DIMENSION=1536
VECTOR_STORE_OPENAI_API_KEY=your-api-key

# HuggingFace Embeddings
VECTOR_STORE_EMBEDDING_PROVIDER=huggingface
VECTOR_STORE_HUGGINGFACE_MODEL=sentence-transformers/all-MiniLM-L6-v2
VECTOR_STORE_HUGGINGFACE_DEVICE=cpu
```

### Retrieval Configuration

```bash
# Hybrid search settings
VECTOR_STORE_RETRIEVAL_STRATEGY=hybrid
VECTOR_STORE_HYBRID_SEARCH_ALPHA=0.7
VECTOR_STORE_HYBRID_SEARCH_KEYWORD_WEIGHT=0.3
VECTOR_STORE_HYBRID_SEARCH_SEMANTIC_WEIGHT=0.7

# Reranking settings
VECTOR_STORE_RETRIEVAL_ENABLE_RERANKING=true
VECTOR_STORE_RETRIEVAL_RERANKING_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
VECTOR_STORE_RETRIEVAL_RERANKING_TOP_K=20
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Store Connection Failed

```bash
# Check if the service is running
# For Qdrant:
docker run -p 6333:6333 qdrant/qdrant
```

#### 2. Out of Memory Errors

```bash
# Reduce batch size
VECTOR_STORE_EMBEDDING_BATCH_SIZE=50

# Use smaller embedding dimension
VECTOR_STORE_EMBEDDING_DIMENSION=384
```

#### 3. Slow Search Performance

```bash
# Enable HNSW indexing
VECTOR_STORE_FAISS_INDEX_TYPE=hnsw
VECTOR_STORE_QDRANT_ENABLE_HNSW_INDEX=true

# Optimize search parameters
VECTOR_STORE_FAISS_HNSW_EF_SEARCH=100
VECTOR_STORE_QDRANT_HNSW_EF_SEARCH=100
```

### Health Checks

```bash
# Check store health
python -m ragbot.cli status

# Detailed performance metrics
python -m ragbot.cli performance
```

## 📚 Examples

### Basic Usage

```python
from ragbot.rag import VectorStoreFactory

# Create a store
store = VectorStoreFactory.create_store("chroma")

# Add documents
documents = [...]
await store.add_documents(documents)

# Search
results = await store.search(query_embedding, top_k=10)
```

### Advanced Usage

```python
from ragbot.rag import VectorStoreFactory
from ragbot.configs.settings import get_settings

# Get configuration
settings = get_settings()
config = settings.vector_store

# Create store with advanced config
store = VectorStoreFactory.create_store(
    config.default_store,
    enable_metadata_filtering=config.enable_metadata_filtering,
    enable_hybrid_search=config.enable_hybrid_search,
    batch_size=config.chroma_batch_size
)

# Advanced search with metadata filtering
results = await store.search_with_metadata_filter(
    query_embedding,
    metadata_filter={"category": "documentation", "priority": "high"},
    top_k=5
)
```

## 📝 Best Practices

### 1. **Development Phase**

- Start with FAISS for quick prototyping
- Use small embedding dimensions (384) for faster iteration
- Enable caching for repeated queries

### 2. **Production Deployment**

- Use Qdrant for high-performance requirements
- Use Chroma for metadata-heavy applications
- Enable monitoring and analytics
- Set up proper backup strategies

### 3. **Performance Optimization**

- Choose appropriate index types (HNSW for speed vs accuracy)
- Optimize batch sizes based on available memory
- Enable GPU acceleration when available
- Use hybrid search for better relevance

### 4. **Monitoring**

```bash
# Enable comprehensive monitoring
VECTOR_STORE_ENABLE_PERFORMANCE_MONITORING=true
VECTOR_STORE_ENABLE_METRICS_COLLECTION=true
VECTOR_STORE_ENABLE_ERROR_TRACKING=true
```

## 🔗 Additional Resources

- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [Chroma Documentation](https://docs.trychroma.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)

## 🆘 Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review the logs for specific error messages
3. Run benchmark tests to identify performance bottlenecks
4. Use the migration tools to switch between stores if needed

For additional support, please refer to the main project documentation or create an issue in the project repository.
