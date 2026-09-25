# 🚀 Quick Start Guide - Vector Stores

## 📋 Overview

Get started with multiple vector stores in TenantRAG API in just a few minutes!

## ⚡ 30-Second Setup

### 1. Install Dependencies

```bash
# Install all vector store clients
pip install -e ".[vectorstores]"
```

### 2. Choose Your Vector Store

```bash
# Option 1: FAISS (Default - No external server required)
export VECTOR_STORE_DEFAULT_STORE=faiss

# Option 2: Chroma (Easy setup)
export VECTOR_STORE_DEFAULT_STORE=chroma

# Option 3: Qdrant (Requires server)
docker run -p 6333:6333 qdrant/qdrant
export VECTOR_STORE_DEFAULT_STORE=qdrant
```

### 3. Run the API Server

```bash
python main.py
# Or: uvicorn ragbot.api.app:app --reload
```

That's it! 🎉

## 🎯 Which Store Should I Choose?

### For Beginners → **FAISS**

```bash
export VECTOR_STORE_DEFAULT_STORE=faiss
# ✅ Works offline, fast setup, good for learning
```

### For RAG Applications → **Chroma**

```bash
export VECTOR_STORE_DEFAULT_STORE=chroma
# ✅ Rich metadata, easy to use, perfect for RAG
```

### For Production → **Qdrant**

```bash
docker run -p 6333:6333 qdrant/qdrant
export VECTOR_STORE_DEFAULT_STORE=qdrant
# ✅ High performance, scalable, distributed vector search
```

## 🔧 Quick Configuration

### Basic Configuration

```bash
# .env file
VECTOR_STORE_DEFAULT_STORE=chroma
VECTOR_STORE_ENABLE_METADATA_FILTERING=true
VECTOR_STORE_ENABLE_HYBRID_SEARCH=true
```

### Store-Specific Configuration

```bash
# FAISS
VECTOR_STORE_FAISS_INDEX_TYPE=hnsw

# Chroma
VECTOR_STORE_CHROMA_PERSIST_DIRECTORY=./chroma_db

# Qdrant
VECTOR_STORE_QDRANT_URL=http://localhost:6333
```

## 🧪 Test Your Setup

### 1. Check Status

```bash
python -m ragbot.cli status
```

### 2. Run Benchmark

```bash
python -m ragbot.cli benchmark-stores --stores faiss chroma
```

### 3. Try Migration

```bash
python -m ragbot.cli migrate-store --source faiss --target chroma
```

## 📚 Common Use Cases

### Case 1: Development & Testing

```bash
# Quick setup for development
export VECTOR_STORE_DEFAULT_STORE=faiss
python main.py
```

### Case 2: Production Deployment

```bash
# High-performance production setup
docker run -d -p 6333:6333 qdrant/qdrant
export VECTOR_STORE_DEFAULT_STORE=qdrant
export VECTOR_STORE_QDRANT_ENABLE_HNSW_INDEX=true
python main.py
```

### Case 3: Metadata-Rich Applications

```bash
# Rich metadata support
export VECTOR_STORE_DEFAULT_STORE=chroma
export VECTOR_STORE_ENABLE_METADATA_FILTERING=true
python main.py
```

## 🛠️ Troubleshooting

### Problem: "Store connection failed"

```bash
# Check if services are running
docker ps  # Should show qdrant container

# Restart services
docker run -p 6333:6333 qdrant/qdrant
```

### Problem: "Dependencies not installed"

```bash
# Install specific dependencies
pip install chromadb          # For Chroma
pip install qdrant-client     # For Qdrant

# Or install all at once
pip install -e ".[vectorstores]"
```

### Problem: "Out of memory"

```bash
# Reduce batch sizes
export VECTOR_STORE_EMBEDDING_BATCH_SIZE=50
export VECTOR_STORE_EMBEDDING_DIMENSION=384
```

## 🚀 Next Steps

### 1. **Read the Full Guide**

Check out [`docs/VECTOR_STORES.md`](VECTOR_STORES.md) for comprehensive documentation.

### 2. **Try Examples**

```bash
python examples/vector_store_examples.py
```

### 3. **Optimize Performance**

```bash
python -m ragbot.cli benchmark-stores
# Use results to choose optimal settings
```

### 4. **Set Up Monitoring**

```bash
export VECTOR_STORE_ENABLE_METRICS=true
export VECTOR_STORE_ENABLE_PERFORMANCE_MONITORING=true
```

## 💡 Pro Tips

### Tip 1: Start Simple

```bash
# Begin with FAISS, then migrate when needed
export VECTOR_STORE_DEFAULT_STORE=faiss
# Later: python -m ragbot.cli migrate-store --source faiss --target chroma
```

### Tip 2: Use Environment Files

```bash
# Create .env file instead of exporting variables
echo "VECTOR_STORE_DEFAULT_STORE=chroma" > .env
echo "VECTOR_STORE_ENABLE_HYBRID_SEARCH=true" >> .env
```

### Tip 3: Test Before Production

```bash
# Always benchmark your specific use case
python -m ragbot.cli benchmark-stores --documents 10000 --dimension 1536
```

### Tip 4: Monitor Performance

```bash
# Enable comprehensive monitoring
export VECTOR_STORE_ENABLE_PERFORMANCE_MONITORING=true
python -m ragbot.cli performance
```

## 🎯 Success Metrics

After setup, you should see:

- ✅ `python -m ragbot.cli status` shows "healthy"
- ✅ Search queries return relevant results
- ✅ Document ingestion works smoothly
- ✅ No error messages in logs

## 🆘 Need Help?

1. **Check Logs**: Look for error messages in the console output
2. **Test Connection**: Use `python -m ragbot.cli status`
3. **Run Examples**: Try `python examples/vector_store_examples.py`
4. **Read Documentation**: See [`docs/VECTOR_STORES.md`](VECTOR_STORES.md)

---

**🎉 You're all set!** Your RAG system now supports multiple vector stores with advanced features. Happy coding! 🚀
