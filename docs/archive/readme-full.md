# Archived Documentation

> [!NOTE]
> This document describes the previous Telegram-based architecture, experiments, or historical roadmap.
> The active production system uses the API-first architecture described in [README.md](../../README.md) and [docs/API.md](../API.md).

---

# RAG Telegram Assistant - Full Documentation

**TL;DR**
- What: Production-grade Telegram RAG assistant (ingest → answer with citations)
- Quick Start: Configure `.env`, set bot token, run `ragbot`, use `/add` and `/ask`
- Core Knobs: Providers (LLM/embeddings), vector store, chunking, retrieval, caching, monitoring
- Extend: Plugins for pre/post ingest/query/response; switch providers; enable analytics

|  | TL;DR |
|---|---|
| 💬 What | Production-grade Telegram RAG assistant (ingest → answer with citations) |
| 🚀 Quick Start | Configure `.env`, set bot token, run `ragbot`, use `/add` and `/ask` |
| ⚙️ Core Knobs | Providers (LLM/embeddings), vector store, chunking, retrieval, caching, monitoring |
| 🧩 Extend | Plugins for pre/post ingest/query/response; switch providers; enable analytics |
| 🔐 Security | Allowlist, rate limits, content safety, optional encryption/secure backups |

## Overview

The RAG Telegram Assistant is a production-ready, multilingual chatbot that leverages Retrieval-Augmented Generation (RAG) to provide intelligent, context-aware answers to user queries. It is designed to process and index various document formats, enabling users to interact with their knowledge base through a Telegram interface. The system supports both online and offline configurations, making it suitable for a wide range of use cases, from personal knowledge management to enterprise-level deployments.

### Problem

Traditional chatbots often lack the ability to provide accurate, context-aware answers, especially when dealing with large or diverse datasets. The RAG Telegram Assistant addresses this by combining document retrieval with advanced language generation, ensuring that responses are both relevant and coherent.

### Scope

The assistant is designed for:

- Individuals seeking a private, intelligent knowledge assistant.
- Organizations needing a secure, scalable solution for document-based Q&A.
- Developers looking for a customizable framework to build advanced chatbots.

### Key Concepts

- **Retrieval-Augmented Generation (RAG)**: Combines document retrieval with language generation to produce contextually accurate answers.
- **Multilingual Support**: Fully functional in English and Persian, with potential for other languages.
- **Extensibility**: Modular architecture allows for easy integration of new features, models, and storage backends.

**Features**

- **User Features**
  - Start/help menus, document ingest (file/URL/text), and Q&A via Telegram.
  - Advanced commands for aggregate/filter/optimize.
  - Citations and friendly references from retrieved chunks.
  - Multi‑format ingestion: PDF, DOCX, TXT, HTML/URL, Markdown, PPTX, XLSX, selected images via OCR.
  - Language support: English/Persian baseline with configurable default.

- **Intelligent Behaviors**
  - Analytics: ML insights, predictive analytics, user segmentation, personalization, churn prediction, anomaly detection, satisfaction tracking.
  - Retrieval adaptivity: dynamically tunes top‑K/thresholds by query complexity; hybrid search + reranking + query expansion; token‑aware context clamping.
  - Semantic reuse: similarity‑based semantic cache with TTL and confidence gating.
  - Graceful degradation: circuit‑breaker‑style fallbacks, per‑service timeouts, cache‑backed responses.

- **Developer & Integration Features**
  - Vector store abstraction with FAISS/Chroma/Qdrant/Weaviate; metadata filters; hybrid search; reranking.
  - Chunking strategies: token/semantic/hierarchical/adaptive (tunable sizes/overlaps).
  - Caching layers: L1 memory, optional L2 Redis, L3 semantic cache.
  - Observability: structured logging, optional Prometheus metrics, health checks, real‑time monitoring, performance/resource dashboards.
  - Multitenancy: tiers with per‑tenant limits, features, audit logs, analytics.

- **Plugin & Extension System**
  - Registry/loader/manager with lifecycle and error handling.
  - Hooks: pre/post ingest, pre/post query, pre/post response, user interaction, and error events.
  - Extensible providers for LLMs, embeddings, stores, and loaders.

**Visual Diagram**

```mermaid
flowchart LR
  A[Ingest Source] --> B[Load & Clean]
  B --> C[Chunk]
  C --> D[Embed]
  D --> E[Vector Store]
  F[User Question] --> G[Retrieve (hybrid/filter/rerank)]
  E --> G
  G --> H[Prompt Build]
  H --> I[LLM Generate]
  I --> J[Answer + Citations]
  J --> K[Semantic Cache (confident)]
```

ASCII fallback:

```
Ingest → Load → Chunk → Embed → [Vector Store]
                 ↑                ↓
            Question → Retrieve → Prompt → Generate → Answer (+Citations)
                                 ↓
                           Semantic Cache (if confident)
```

**Design Rationale (Why)**
- Redis is optional: Runs well with in‑process L1 and semantic reuse; optional Redis reduces infra overhead and keeps local/dev simple. Enable for cross‑process caching when needed.
- Adaptive chunking: Preserves structure and improves retrieval while respecting token budgets; static sizes can fragment semantics.
- Hybrid + reranking: Combining lexical and semantic signals improves robustness across query styles; reranking sharpens top results.
- Score convention (higher is better): Normalization across backends avoids confusion and simplifies tuning.
- Optional HTTP endpoints: Telegram‑first posture with optional metrics/health reduces exposed surface in minimal deployments.
- Multi‑provider architecture: Swappable providers avoid lock‑in and permit cost/perf trade‑offs.
- Confidence‑gated semantic cache: Only caches high‑confidence answers to reduce stale reuse.

**Detailed Feature Matrix**

- RAG Core
  - Loaders: Ingest PDF, DOCX, TXT, HTML/URL, Markdown, PPTX, XLSX, selected images via OCR; structural extraction (headings, links, tables, images), HTML user‑agent/header controls, retries/timeouts, language detection toggles.
  - Chunkers: Token, semantic, hierarchical, adaptive; tunable sizes/overlaps; semantic thresholds; token counting and token‑safe truncation helpers.
  - Embeddings: Providers for cloud/local (OpenAI, HuggingFace, Sentence‑Transformers), batch size/timeout/control, optional local cache folder.
  - Store: Pluggable FAISS/Chroma/Qdrant/Weaviate; IVF/HNSW tuning; GPU optional; metadata filtering; backup/restore helpers; store analytics and metrics.
  - Retrieval: Basic retriever with dynamic top‑K/thresholds and post‑filtering; advanced retriever combining hybrid search, query expansion, and Cross‑Encoder reranker; confidence thresholding; deduplication; expansion/rerank caching and timeouts.
  - Query: Rich filters (equals/gt/gte/lt/lte/in/nin/contains/regex/exists/range/geo); composite AND/OR/NOT; aggregations (count/sum/avg/min/max/median/std/variance/percentile); query optimizer with index hints, cache optimization, parallelization, filter pushdown, result limiting, early termination.
  - QA Chain: Prompt building, multi‑provider LLMs (OpenRouter/OpenAI/Anthropic/Ollama/HF local), structured output via instructor, heuristic confidence scoring, token‑budget clamping, cleanup for clients/pipelines.

- Caching
  - L1 memory cache; optional L2 Redis (ping/auto‑disable on failure); L3 semantic cache by embedding similarity with TTL, eviction, and hit/miss analytics; embedding cache for reuse.

- Security
  - User allowlist, rate limiting with sliding windows and temporary blocks, content filtering (spam/toxicity), encryption/key management/secure backups, optional key rotation; size/type validation for uploads.

- Multi‑Tenant
  - Tenants with tiers, plans, limits, and features; isolation/audit logging; user management and auth; usage/billing/metrics models; tenant analytics and security reports.

- Analytics
  - Usage patterns, dashboards, satisfaction tracking; ML insights and predictive analytics; per‑user and tenant‑level analytics hooks.

- Monitoring & Outputs
  - Real‑time monitor, periodic health checks, performance/resource dashboards, optimization engine; Prometheus metrics across documents/queries/retrieval/LLM/errors/resources; optional HTTP health endpoints (live/ready/detailed/components/metrics).

- Plugins
  - Registry/loader/manager with lifecycle, reload/unload, auto‑load; hook points (pre/post ingest/query/response, user interaction, error); validation/registry persistence.

- Services
  - Orchestrated ingest (validate → load → chunk → embed → store → encrypt/backup optional), query (retrieve → optimize → rerank → answer → cite → cache), batch ingest, resets, health summaries; graceful degradation with per‑service timeouts and fallbacks.

- App & CLI
  - Telegram bot with modular routers (ingest, QA, analytics, monitoring, performance, plugins, admin, security), UI keyboards; CLI for ingest, batch‑ingest, query, reset, status, performance/resource summaries, vector store migration/verification.

- Configuration
  - Comprehensive typed settings for LLM/embeddings/RAG/retrieval/store/vector‑store/security/multi‑format/plugins/monitoring/performance/analytics/Redis/database/advanced‑chunking/semantic‑cache with env overrides, path creation, and full validation.

**Vector Store Selection Guide**
- FAISS: local/offline, small–medium datasets, Flat/IVF/HNSW, optional GPU.
- Chroma: metadata‑rich RAG, persistent collections, HNSW, simple ops.
- Qdrant: large datasets/production, HNSW, payload indexing, robust API.
- Weaviate: enterprise + multi‑modal/GraphQL, powerful schema and queries.

**Quick Config Toggles (examples)**
- Vector DB/provider: choose store and adjust HNSW/IVF/batch sizes and filters.
- Retrieval: hybrid/reranking/expansion toggles; top‑K and thresholds; context budgets.
- Caching: Redis on/off; semantic cache similarity/TTL/eviction.
- Monitoring: metrics and real‑time intervals/thresholds; async worker limits.
- Security: allowlist, rate limits, file size/types, encryption/rotation.

## Architecture

### Main Components

1. **Telegram Bot Interface**: Handles user interactions, including commands and queries.
2. **Document Ingestion Pipeline**: Processes and indexes documents for retrieval.
3. **RAG Core**: Implements the retrieval and generation logic.
4. **Vector Database**: Stores embeddings for efficient similarity search.
5. **Monitoring and Logging**: Tracks system health and performance.
6. **Security Layer**: Ensures data privacy and access control.

### Data Flow

1. **User Input**: Queries or documents are sent via Telegram.
2. **Processing**: Documents are chunked, embedded, and stored; queries are converted to vectors.
3. **Retrieval**: Relevant document chunks are retrieved based on vector similarity.
4. **Generation**: Retrieved chunks are combined with the query to generate a response.
5. **Output**: The response is sent back to the user.

### Key Dependencies

- **aiogram**: For Telegram bot interactions.
- **LangChain**: For RAG pipeline implementation.
- **FAISS/Chroma/Qdrant**: For vector storage.
- **Transformers**: For embedding and language generation.
- **Redis**: For caching.

## Features

### User-Visible Features

- **Document Upload**: Supports PDF, DOCX, TXT, and URLs.
- **Query Answering**: Provides context-aware answers to user queries.
- **Multilingual Support**: Handles queries in English and Persian.
- **Command Interface**: `/start`, `/add`, `/ask`, `/reset`, `/help`, `/config`.

### Internal Capabilities

- **Advanced Chunking**: Token-based, semantic, and hierarchical chunking strategies.
- **Hybrid Retrieval**: Combines vector similarity with metadata filtering.
- **Caching**: Two-tier caching for embeddings and responses.
- **Monitoring**: Prometheus metrics and structured logging.
- **Security**: User allowlist, rate limiting, and encryption.

## Configuration

### Environment Variables

- **BOT_TOKEN**: Telegram bot token.
- **LLM_PROVIDER**: Language model provider (e.g., OpenAI, HuggingFace).
- **VECTOR_DB**: Vector database backend (e.g., FAISS, Chroma).
- **CACHE_TTL**: Time-to-live for cached items.

### Defaults

- **Chunk Size**: 400 tokens.
- **Top-K Retrieval**: 5 chunks.
- **Similarity Threshold**: 0.6.

### Examples

```env
BOT_TOKEN=your-telegram-bot-token
LLM_PROVIDER=openai
VECTOR_DB=faiss
CACHE_TTL=1800
```

## Setup & Usage

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running Locally

1. Configure the environment:
   ```bash
   cp env.example .env
   nano .env
   ```
2. Start the bot:
   ```bash
   python main.py
   ```

### Docker Deployment

1. Build and run the Docker container:
   ```bash
   docker compose up --build -d
   ```

## APIs/Interfaces

### CLI Commands

- **Status**: `python -m ragbot.cli status`
- **Ingest Document**: `python -m ragbot.cli ingest --file <path>`
- **Query**: `python -m ragbot.cli query --question "What is RAG?"`

### HTTP Endpoints

- **Health Check**: `/health`
- **Metrics**: `/metrics`

### Extension Points

- **Plugins**: Dynamic loading and hot-swapping.
- **Custom Models**: Add new LLMs or embedding models.

## Data & Storage

### Schemas

- **Documents**: Metadata and embeddings.
- **Users**: Access control and preferences.

### Migrations

- Managed via Alembic.

### Caching

- **Redis**: Stores embeddings and responses.

### Queues

- **Async Tasks**: For long-running operations.

## Security & Permissions

### Authentication

- **User Allowlist**: Restricts access to specific Telegram IDs.

### Secrets Handling

- Stored in `.env` file.

### Sensitive Data

- Encrypted at rest and in transit.

## Performance & Limits

### Bottlenecks

- **Embedding Generation**: Can be slow for large documents.
- **Vector Search**: Performance depends on database choice.

### Scaling

- Horizontal scaling via Docker Swarm or Kubernetes.

### Resource Requirements

- **CPU**: Minimum 4 cores.
- **RAM**: Minimum 8 GB.

## Testing & QA

### Running Tests

- **Unit Tests**: `pytest tests/unit`
- **Integration Tests**: `pytest tests/integration`
- **Coverage**: `pytest --cov=ragbot`

### CI Overview

- GitHub Actions for automated testing and linting.

## Deployment

### Environments

- **Development**: Local setup with `.env`.
- **Production**: Dockerized deployment.

### Build/Release Process

- Managed via Makefile and Docker Compose.

### Monitoring/Health

- Prometheus and Grafana dashboards.

## Troubleshooting

### Common Errors

- **Invalid Token**: Check `BOT_TOKEN` in `.env`.
- **Connection Timeout**: Verify database and Redis connections.

### Logs to Check

- `logs/ragbot.log`

### Recovery Steps

- Restart the bot: `docker restart ragbot`.
- Clear cache: `redis-cli FLUSHALL`.

## Roadmap / Gaps

### Known TODOs

- Add support for additional languages.
- Improve OCR accuracy.

### Deprecated Areas

- Legacy chunking methods.

### Suggested Improvements

- Implement GPU acceleration for embeddings.
- Add more advanced analytics.

---

This README provides a comprehensive overview of the RAG Telegram Assistant, covering its architecture, features, and usage. For further details, consult the source code and documentation.
