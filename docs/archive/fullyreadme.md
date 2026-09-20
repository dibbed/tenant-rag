# Archived Documentation

> [!NOTE]
> This document describes the previous Telegram-based architecture, experiments, or historical roadmap.
> The active production system uses the API-first architecture described in [README.md](../../README.md) and [docs/API.md](../API.md).

---

﻿**RAG Telegram Assistant — Full Project README**

- Production‑ready Retrieval‑Augmented Generation (RAG) assistant delivered as a Telegram bot
- Multi‑format ingestion, advanced retrieval, semantic caching, analytics, monitoring, and a pluggable architecture

**TL;DR**
- What: A production-grade Telegram assistant that ingests your documents and answers questions using a flexible RAG pipeline (load → chunk → embed → retrieve → generate), with strong observability, security, plugins, and multitenancy.
- Quick start: set environment (.env), provide a bot token and model/vector store settings, then run `ragbot` (or use Docker Compose). Use `/add` to ingest and `/ask` to query.
- Core knobs: choose LLM/embedding provider, vector store backend, chunking strategy, retrieval/reranking toggles, caching layers, and security/monitoring levels.
- Extend: add plugins (pre/post ingest/query/response hooks), switch providers, enable advanced analytics, or run locally with HF/Ollama.

|  | TL;DR |
|---|---|
| 💬 What | Production-grade Telegram RAG assistant (ingest → answer with citations) |
| 🚀 Quick Start | Configure `.env`, set bot token, run `ragbot`, use `/add` and `/ask` |
| ⚙️ Core Knobs | Providers (LLM/embeddings), vector store, chunking, retrieval, caching, monitoring |
| 🧩 Extend | Plugins for pre/post ingest/query/response; switch providers; enable analytics |
| 🔐 Security | Allowlist, rate limits, content safety, optional encryption/secure backups |

**Overview**
- Purpose: Provide an end‑to‑end assistant that ingests documents (files, URLs, text), builds vector indexes, and answers questions grounded in your content via Telegram.
- Scope: Covers ingestion (load → chunk → embed → store), querying (retrieve → rank → prompt → generate), observability (metrics, health), security (filters, encryption), multitenancy, and a plugin system for extension.
- Key Concepts:
  - RAG pipeline: decoupled loaders, chunkers, embedders, vector stores, retrievers, and a QA chain that orchestrates LLM calls.
  - Advanced retrieval: hybrid search, reranking, query expansion, custom scoring, and optimization.
  - Caching: multi‑level (memory, Redis) plus semantic cache for answer reuse.
  - Telegram interface: commands and inline actions for ingest, query, admin, analytics, monitoring, and plugins.

**Architecture**
- Main Components
  - Application: Telegram bot with routers for commands, callbacks, admin, analytics, security, monitoring, and advanced queries.
  - RAG Core: loaders (multi‑format), chunkers (semantic/token/hierarchical/adaptive), embeddings (local/cloud), vector store abstractions, retrieval, and QA chain.
  - Services: an integration layer that wires everything together; an orchestrating service that exposes ingest/query/health and optional graceful degradation.
  - Caching: in‑memory, optional Redis, and a semantic cache indexed by embedding similarity.
  - Security: content filtering, rate limiting, encryption and key management, secure backups.
  - Analytics & Monitoring: metrics manager (Prometheus optional), performance/resource dashboards, real‑time monitor, health checks/endpoints.
  - Plugins: loader/registry/manager with hooks for pre/post ingest/query/response and error handling.
  - Multitenancy: tenant manager/auth/analytics with tiered features and limits.
- Data Flow (high level)
  - Ingest: source → loader (by type) → chunker → embedder → vector store (with metadata) → metrics → optional encryption/backup.
  - Query: question → retrieve (hybrid/filters/rerank) → prompt builder → LLM → answer + citations → semantic cache (if confident) → analytics.
- Dependencies (not exhaustive): Telegram framework, async runtime, optional Prometheus, optional Redis, LLM/embedding providers, and vector DB backends. The system degrades gracefully when optional parts are absent.

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

**Configuration**
- How configuration works
  - Central settings object composed of sub‑settings for LLM, embeddings, RAG, vector store, store backend, performance, monitoring, security, multi‑format loaders, analytics, Redis, database, advanced chunking, semantic cache, and plugins.
  - Values come from environment variables (and `.env`) with validation and sensible defaults.
- Common environment variables (examples)
  - Core: `BOT_TOKEN`, `DEBUG=false`, `DEFAULT_LANG=en`, `DATA_DIR=./data`.
  - LLM: `LLM_PROVIDER=openrouter|openai|anthropic|ollama|hf_local`, `LLM_MODEL=...`, optional `LLM_BASE_URL`, and provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`).
  - Embeddings: `EMBED_PROVIDER=openai|huggingface|sentence_transformers`, `EMBED_MODEL=...`, `EMBED_BATCH_SIZE=100`.
  - Vector store selection: `VECTOR_DB=faiss|chromadb|qdrant|weaviate` plus provider‑specific options (collection, URL, vector sizes, HNSW/IVF params, batch sizes).
  - RAG: `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`, `RAG_TOP_K`, similarity thresholds, OCR toggles.
  - Redis: `ENABLE_REDIS=true|false`, `REDIS_URL=redis://...`.
  - Monitoring/Performance: enable metrics, real‑time monitoring intervals, thresholds, max concurrent workers/tasks, memory limits, timeouts registry.
  - Security: `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW`, max file size, allowed file types, user allowlist.
  - Semantic cache: enable/disable, similarity threshold, TTL, eviction.
  - Plugins: enable auto‑load, plugin directory.
- Notes
  - Provider‑specific keys are only required when the corresponding provider is selected.
  - Paths are created automatically where configured (logs, store, data).
  - A comprehensive validation routine flags errors/warnings (e.g., missing keys, invalid intervals).

**Setup & Usage**
- Local
  - Create a virtual environment and install requirements: `pip install -r requirements.txt` (or a stable constraints file if provided).
  - Copy environment template to `.env` and set `BOT_TOKEN` and provider keys.
  - Run the bot locally via the console script (e.g., `ragbot`)..
- Docker
  - Build and run with compose: `docker compose up --build`.
  - Mount data/logs to persist vector indexes and logs; expose metrics port only when needed.
- CLI (typical flows)
  - Ingest a file/URL/text: `ragbot-cli ingest --file doc.pdf` | `--url https://...` | `--text "..."`.
  - Batch ingest: `ragbot-cli batch-ingest --dir ./docs --pattern "*.pdf" --recursive`.
  - Query: `ragbot-cli query --question "What is RAG?" --lang en --top-k 4`.
  - Maintenance: `ragbot-cli status`, `ragbot-cli reset`.
  - Migration: `ragbot-cli migrate --source faiss --target chromadb` (and verification subcommands).
- Telegram
  - `/start` shows the main menu; `/help` lists features.
  - `/add` to ingest (supports sending a file, URL, or inline text).
  - `/ask` for Q&A; advanced commands for aggregate/filter/optimize are also available.

**APIs / Interfaces**
- Telegram Bot
  - Commands: start/help/add/ask and advanced query/admin/monitoring actions mapped to inline menus and callbacks.
  - Middleware: auth (allowlist), rate limiting, optional content filtering on both messages and callbacks.
- CLI
  - Commands for ingest, batch‑ingest, query, reset, status, performance, and vector store migration/verification; all route through the integration/service layers.
- HTTP (optional)
  - Health endpoints (if the lightweight HTTP app is initialized) for liveness/readiness/basic/ detailed health and metrics exposure suitable for orchestration and monitoring systems.
- Plugin Hooks
  - Pre/Post hooks for document ingest, query, response, user interaction, and error events; plugins register lifecycle and hook callbacks via the manager.

**Data & Storage**
- Logical schema (high level)
  - Vector document: `{ id, content, embedding, metadata, score? }` with a “higher is better” score convention across backends.
  - Chunk metadata commonly includes source identifiers, chunk indices, spans, page/slide hints, and structure markers.
- Vector Stores
  - Pluggable backends with normalized search APIs; support metadata filters, hybrid scoring, and reranking.
- Migrations
  - Utilities for migrating between providers and verifying counts/consistency; supports batch sizes and progress reporting.
- Caching
  - L1 in‑memory, optional L2 Redis for cross‑process reuse, and L3 semantic cache keyed by embedding similarity with TTL and eviction.
- Queues
  - Async pipelines use cooperative concurrency; no external queue is required by default.

**Design Rationale (Why)**
- Redis is optional: The system runs well with in‑process L1 caching and semantic reuse; making Redis optional reduces infra overhead, eases local/dev usage, and preserves portability. When enabled, Redis provides shared, cross‑process caching.
- Adaptive chunking: Static chunk sizes can fragment semantics or blow token budgets. Adaptive/semantic strategies preserve structure and improve retrieval recall while keeping prompts concise.
- Hybrid + reranking: Combining lexical and semantic signals improves robustness across short/long or keyword/semantic queries. Reranking sharpens the top set without over‑fetching.
- Score convention (higher is better): Normalizing scores across backends eliminates ambiguity (L2 distance → negative similarity) and simplifies tuning and evaluation.
- Optional HTTP endpoints: The assistant is Telegram‑first. Keeping HTTP health/metrics optional avoids unnecessary exposed ports in minimal deployments.
- Multi‑provider architecture: Swappable LLM/embedding/store providers prevent lock‑in and allow cost/performance trade‑offs per environment.
- Confidence‑gated semantic cache: Caching only high‑confidence answers reduces stale or incorrect reuse and keeps behavior predictable.

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
- FAISS
  - Best for: local/offline, small–medium datasets, fast prototyping.
  - Strengths: very fast, low overhead; supports Flat/IVF/HNSW; optional GPU.
  - Notes: ideal default for local dev; pair with semantic cache for reuse.
- Chroma
  - Best for: rich metadata filtering and straightforward RAG apps.
  - Strengths: persistent collections, metadata filters, simple ops.
  - Notes: good balance of features + ease; supports HNSW tuning.
- Qdrant
  - Best for: large datasets and production environments.
  - Strengths: high performance, HNSW, payload indexing, robust API.
  - Notes: tune HNSW and batching; great for scale and latency SLOs.
- Weaviate
  - Best for: enterprise and multi‑modal/GraphQL‑centric apps.
  - Strengths: GraphQL, multi‑modal options, cloud‑friendly.
  - Notes: powerful schema + query semantics; plan per‑tenant classes if needed.

**Quick Config Toggles (examples)**
- Select store/provider
  - Vector DB: set to `faiss`, `chromadb`, `qdrant`, or `weaviate`.
  - Store tuning: enable metadata filtering, hybrid search, reranking; adjust HNSW/IVF params and batch sizes.
- Retrieval behaviors
  - Hybrid search on/off; reranking model/threshold; query expansion type and limits.
  - Top‑K, similarity thresholds, and token/context budgets.
- Caching
  - Enable/disable L2 Redis; semantic cache similarity threshold, TTL, eviction.
- Monitoring/Performance
  - Enable metrics/real‑time monitoring; set intervals, alert thresholds, async worker limits.
- Security
  - Allowlist, rate limits, max file size/types, encryption and key rotation.

**Security & Permissions**
- Authentication/Authorization
  - Telegram user allowlist (empty list can be treated as allow‑all if desired); admin actions are gated by role/menus.
  - Per‑user rate limiting with sliding window and temporary blocking under sustained abuse.
- Content Safety
  - Content filter middleware; optional spam/toxicity checks; configurable file‑type allowlist and maximum sizes.
- Secrets & Data Handling
  - API keys read from environment; encryption manager supports encrypting content/metadata/embeddings and secure backups; key rotation and keystore abstraction included.
  - Sensitive logs are minimized; structured logging routes to file and optional JSON alongside console.

**Performance & Limits**
- Tuning knobs
  - Chunking sizes/overlaps, retrieval top‑K and thresholds, hybrid/reranking toggles, async worker limits, batch sizes, and semantic cache settings.
- Monitoring
  - Prometheus metrics (optional), performance/resource dashboards, real‑time monitoring, and periodic health checks.
- Known considerations
  - CPU/GPU requirements depend on embedding/LLM providers and vector store configuration; long documents may require higher memory or chunk tuning.

**Testing & QA**
- Local checks
  - Validate configuration: ensure provider keys and bot token are set; run a quick ingest/query round‑trip with a small document.
  - Use the CLI `status` and `performance` commands to confirm health/metrics.
- Automated
  - The codebase includes extensive validation utilities and internal health checks. If adding tests, focus on RAG orchestration, retrieval correctness (scores/filters), and config validation.

**Deployment**
- Environments
  - Local (single process), Docker/Compose for consistency, and orchestrated environments with liveness/readiness/metrics where enabled.
- Build & Release
  - Container image installs dependencies, copies the project, and starts the bot; mount data/logs for persistence.
- Runtime Assumptions
  - Outbound network access for Telegram and any remote model/vector providers; metrics port only needed if Prometheus is used.
- Monitoring & Health
  - Structured logs, optional Prometheus scraping, health endpoints (if HTTP enabled), and system/resource checks.

**Troubleshooting**
- Pydantic/OpenAI version mismatch
  - Pin compatible versions if you see `__pydantic_*` errors.
- Windows async loop issues
  - Avoid optional loop optimizations not supported on Windows; install only cross‑platform dependencies.
- Redis unavailable
  - Disable Redis in configuration to run without L2 cache; the system will fall back to memory cache.
- Vector store connectivity
  - Verify provider URLs/paths and collection names; ensure vector dimensions match the embedding model.
- LLM timeouts or provider errors
  - Use graceful degradation, increase timeouts, or switch providers; check rate limits and API keys.

**Roadmap / Gaps**
- HTTP service wrapper for health/metrics by default (currently optional).
- Expanded plugin marketplace and example plugins.
- Persistent multitenant metadata and policy storage beyond in‑memory defaults.
- Additional vector stores and cloud backends; richer hybrid/reranking strategies.
- More robust test coverage for edge cases and integrations.
- Unified English documentation across all modules; some internal comments remain multilingual.

**Assumptions & Notes**
- The project centers on a Telegram interface; HTTP endpoints are optional and only used when explicitly enabled.
- Some advanced features are provider‑dependent; when an optional dependency is missing, components degrade gracefully.
- Root‑level docs are treated as more current; deeper docs may lag behind implementation.
