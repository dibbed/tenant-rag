# RAGBot - API-First Retrieval-Augmented Generation Backend

[![CI](https://github.com/dibbed/rag-telegram-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/dibbed/rag-telegram-assistant/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)

High-performance, production-ready Python backend providing an **API-first Retrieval-Augmented Generation (RAG)** platform over documents (PDF, DOCX, TXT, HTML, Markdown, PPTX, XLSX, images/OCR) and web URLs. Features native multilingual support (English and Persian), multi-tier semantic caching, thread-safe and async-safe vector storage (FAISS, Chroma, Qdrant, Weaviate), sliding-window rate limiting, and broad LLM support (OpenAI, Anthropic Claude, Ollama, HuggingFace, OpenRouter).

*Persian Documentation: [README.fa.md](README.fa.md) · Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · REST API: [docs/API.md](docs/API.md)*

---

## 🏛️ System Architecture

```text
Frontend / Web Client / External Systems
                  ↓
       FastAPI HTTP API Server
    ├── RateLimitMiddleware (Sliding Window)
    ├── CORS Middleware
    └── Exception & Validation Handlers
                  ↓
       Service Orchestration Layer
    ├── IntegrationService (Lifespan Component Management)
    └── RAGService (Document Ingestion, Query Pipelines, Store Resets)
                  ↓
       Multi-Tier Caching System
    ├── SemanticCache (Cosine Similarity Answer Reuse)
    └── L1/L2 General Cache (Memory / Redis)
                  ↓
       RAG Core Pipeline
    ├── Loaders (PDF, DOCX, TXT, HTML, MD, PPTX, XLSX, OCR)
    ├── Chunkers (Token, Semantic, Hierarchical, Adaptive)
    ├── Embeddings (SentenceTransformers, OpenAI, HuggingFace)
    ├── Vector Stores (FAISS with async_lock, Chroma, Qdrant, Weaviate)
    └── QAChain (OpenAI, Anthropic Claude, Ollama, HuggingFace)
```

---

## 🚀 Quick Start

### 1. Environment Setup

Clone repository and create virtual environment:

```bash
git clone https://github.com/dibbed/rag-telegram-assistant.git
cd rag-telegram-assistant

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -U pip
pip install -r requirements.txt
```

### 2. Configuration

Copy `env.example` to `.env` and set desired settings:

```bash
cp env.example .env
```

Minimal `.env` for free local testing:
```env
# Server
HOST=0.0.0.0
PORT=8000

# LLM Provider (options: openrouter, openai, anthropic, ollama, hf_local)
LLM_PROVIDER=openrouter
LLM_MODEL=x-ai/grok-4-fast:free
OPENROUTER_API_KEY=your_key_here

# Embeddings (Sentence Transformers runs offline on CPU)
EMBED_PROVIDER=sentence_transformers
EMBED_MODEL=intfloat/e5-small-v2

# Vector Store (faiss, chroma, qdrant, weaviate)
VECTOR_STORE_DEFAULT_STORE=faiss
```

### 3. Start the API Server

```bash
# Using Python entry point:
python main.py

# Or via Uvicorn directly:
uvicorn ragbot.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI documentation is immediately available:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 📡 Core API Endpoints

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/health` or `/api/v1/health` | Subsystem health check (vector store, embeddings, cache, LLM) |
| `POST` | `/api/v1/query` | Ask questions with grounded source citations and confidence metrics |
| `POST` | `/api/v1/documents/upload` | Upload and ingest document files (PDF, DOCX, TXT, HTML, MD, etc.) |
| `POST` | `/api/v1/documents/text` | Ingest direct text content into the knowledge base |
| `POST` | `/api/v1/documents/url` | Ingest content from a web URL |
| `POST` | `/api/v1/documents/reset` | Clear all vector store documents and invalidate semantic caches |

### Example: Querying the Knowledge Base

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the primary architecture of this system?",
    "language": "en",
    "top_k": 3,
    "similarity_threshold": 0.5
  }'
```

**Response:**
```json
{
  "answer": "The system follows an API-first RAG architecture orchestrated via FastAPI...",
  "sources": ["architecture_overview.pdf (Page 2)"],
  "confidence_score": 0.92,
  "processing_time": 0.84,
  "language": "en",
  "retrieved_chunks": 3,
  "metadata": {}
}
```

### Example: Ingesting Plain Text

```bash
curl -X POST "http://localhost:8000/api/v1/documents/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Retrieval-Augmented Generation enhances LLM responses by fetching context.",
    "title": "rag_intro",
    "metadata": {"category": "ai"}
  }'
```

---

## ⚙️ Configuration & Providers

### Supported LLM Providers

| Provider | `LLM_PROVIDER` | Default Model | Required Credentials |
|:---|:---|:---|:---|
| **OpenAI** | `openai` | `gpt-3.5-turbo` / `gpt-4o` | `OPENAI_API_KEY` |
| **Anthropic** | `anthropic` | `claude-3-haiku-20240307` | `ANTHROPIC_API_KEY` |
| **OpenRouter** | `openrouter` | `x-ai/grok-4-fast:free` | `OPENROUTER_API_KEY` |
| **Ollama (Local)** | `ollama` | `llama2` / `llama3` | Local server (`http://localhost:11434`) |
| **HuggingFace (Local)** | `hf_local` | Local checkpoint | PyTorch environment |

### Supported Vector Databases

- **FAISS** (Default): In-memory index with persistent disk storage. Hardened with class-level `async_lock` to ensure concurrent write safety and prevent file lock collisions.
- **Chroma**: Embedded metadata-rich vector store.
- **Qdrant**: High-performance vector store with HNSW indexing and clustering support.
- **Weaviate**: Enterprise vector store with GraphQL capabilities.

See [docs/VECTOR_STORES.md](docs/VECTOR_STORES.md) for database-specific configuration.

---

## 🛡️ Security & Rate Limiting

- **Sliding-Window Rate Limiting**: In-memory rate limiting middleware per client IP address. Configured via `SECURITY_RATE_LIMIT_REQUESTS=60` and `SECURITY_RATE_LIMIT_WINDOW=60`. Exceeding limits returns `HTTP 429 Too Many Requests` with standard `Retry-After` headers.
- **Path Sanitization**: Uploaded files and metadata keys are sanitized against directory traversal attacks.
- **Payload Constraints**: Maximum document text payloads and file uploads enforced via `SECURITY_MAX_FILE_SIZE_MB=50` (returns `HTTP 413` when exceeded).

---

## 🧪 Testing

Testing strictly enforces CPU execution to prevent GPU allocation collisions:

```powershell
# Windows (PowerShell):
$env:CUDA_VISIBLE_DEVICES = ""
$env:TORCH_DEVICE = "cpu"
.\venv\Scripts\pytest.exe -o addopts='' -q

# Linux/macOS:
export CUDA_VISIBLE_DEVICES=""
export TORCH_DEVICE="cpu"
pytest -o addopts='' -q
```

Detailed testing guide: [docs/testing.md](docs/testing.md).

---

## 🐳 Docker Deployment

```bash
docker compose up --build -d
```

Mounts `./data`, `./logs`, and model caches for offline operations. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployments.

---

## 📚 Documentation Index

- [Architecture Guide](docs/ARCHITECTURE.md)
- [REST API Specification](docs/API.md)
- [Configuration Reference](docs/configuration.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Testing Guide](docs/testing.md)
- [Vector Stores Guide](docs/VECTOR_STORES.md)
- [Multi-Format Document Support](docs/MULTI_FORMAT_SUPPORT.md)
- [Usage Examples](docs/EXAMPLES.md)
- [Historical Archive](docs/archive/)

---

## 📄 License

MIT License © 2025–2026 [dibbed](https://github.com/dibbed).
