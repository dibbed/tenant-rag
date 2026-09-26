# Changelog

All notable changes to the RAGBot project are documented in this file.

## 2026-09-26: Security Verification Pipeline

- **Verification Pipeline**: `.github/workflows/ci.yml` runs the full test suite and a separate Security Regression Suite on Python 3.10, 3.11 and 3.12, a Dependency Vulnerability Check (pip-audit with the OSV database), a Container Build Check and report-only Ruff, MyPy and Bandit checks, and writes a Verification Summary for every run. Details: `docs/features/security-verification-pipeline/README.md`.
- **Security Regression Suite**: a failed, skipped, removed or unlisted security test fails the check. The test list is `tests/security/suite_manifest.json`.
- **Dependency remediation**: removed the unused langchain, langchain-openai, langchain-community and nltk; moved chromadb to the optional `vectorstores` extra; upgraded fastapi to 0.141.1 (starlette 1.7.0), aiohttp to 3.14.3, cryptography to 50.0.1, pyjwt to 2.15.0, orjson to 3.12.0, Pillow to 12.3.0, pypdf to 6.19.0, requests to 2.34.2, torch to 2.14.0, transformers to 5.17.0, sentence-transformers to 6.1.0 and mkdocs-material to 9.7.7. The dependency check has no accepted exceptions.
- **Local checks**: `make verify` and `scripts/verify_pipeline.sh` run the same checks.
- **Test Suite Pass**: 1005 passed, 11 skipped, 0 failed; Security Regression Suite 322 passed, 0 skipped.

## 2026-09-24 — Tenant Authentication, Authorization & API Security Hardening

- **Decoupled Identity & Routing**: Enforced zero-trust separation between identity authentication (`X-API-Key: rgb_<token>` or `Authorization: Bearer <token>`) and routing headers (`X-Tenant-ID`). Requests attempting cross-tenant access are strictly blocked with `HTTP 403 Forbidden`. Requests lacking credentials in multi-tenant mode return `HTTP 401 Unauthorized`.
- **Cryptographic Credential Storage**: Built persistent SQLite credential store (`tenant_api_keys` table in `data/tenants/tenants.db`). Raw keys follow `rgb_<secrets.token_urlsafe(32)>` format, displayed only upon generation. Only SHA-256 hashes (`key_hash`) are persisted with B-tree indexes.
- **Immediate Revocation**: Added immediate persistent key revocation with SQLite deactivation and in-memory cache invalidation.
- **Reset Authorization Protection**: Guarded `/api/v1/documents/reset` with RBAC requiring `admin` or `super_admin` role. Non-admin principals receive `HTTP 403 Forbidden`.
- **CLI Key Management**: Added subcommands under `ragbot-cli tenant`: `create-api-key`, `revoke-api-key`, and `list-api-keys` with secret masking.
- **Test Suite Pass**: Achieved 627 passed, 1 skipped, 0 failed across full test suite.

## 2026-09-22 — Multi-Tenant Subsystem & Plugin Architecture Restoration

- **Multi-Tenant Subsystem Restoration**: Restored `ragbot/multi_tenant/` with durable SQLite persistence (`tenants.db`) with WAL mode and `asyncio.Lock()` protection.
- **Hard Vector Store & Cache Isolation**: Partitioned FAISS (tenant directories), Chroma/Qdrant (tenant collections), and SemanticCache (tenant key prefixing and cosine similarity filtering).
- **Plugin Architecture Restoration**: Restored `ragbot/plugins/` with `PluginManager`, lifecycle integration (`lifespan`), and standard hook points (`PRE/POST_DOCUMENT_INGEST`, `PRE/POST_QUERY`, `PRE/POST_RESPONSE`).
- **Observable Failure Isolation**: Plugin hook exceptions are isolated and logged as warnings; faulty plugins cannot crash host request processing.
- **CLI Management**: Added `ragbot-cli tenant` and `ragbot-cli plugin` administrative commands.

## 2026-09-20 — Core Remediation & Production Hardening

- **Vector Store Concurrency Safety**: Protected `FAISSVectorStore` against race conditions and Windows file sharing collisions (`[WinError 32]`) by wrapping document additions, updates, deletions, clears, and disk saves in an asynchronous class-level lock (`async_lock`).
- **Cache Lifecycle Unification**: Unified semantic cache ownership under `CacheManager.semantic_cache`, added `clear` method alias to `SemanticCache`, and aligned `RAGService.reset_store()` and `/api/v1/documents/reset` to invalidate all active cache layers when the store is reset.
- **API Abuse Prevention & Validation**: Implemented `RateLimitMiddleware` using a thread-safe sliding-window counter per client IP address returning standard RFC `HTTP 429` headers. Added `HTTP 413` payload size validation on direct text ingestion routes.
- **Provider Integrity**: Added native Anthropic Claude (`anthropic.AsyncAnthropic`) support to `QAChain` using the Messages API.
- **Bytecode Artifact Purge**: Removed orphaned legacy Telegram bytecode artifacts (`ragbot/app/`).
- **Test Suite Pass**: Achieved 593 passed, 2 skipped, 0 failed across unit, integration, and API test suites in CPU isolation.

## 2026-09-18 — Telegram Transport Migration to API-First Architecture

- **Transport Migration**: Decommissioned `aiogram 3` Telegram transport layer and established a modern, modular **FastAPI** HTTP REST API application layer under `ragbot/api/`.
- **API Endpoints**: Introduced `/health`, `/api/v1/health`, `/api/v1/query`, `/api/v1/documents/upload`, `/api/v1/documents/text`, `/api/v1/documents/url`, and `/api/v1/documents/reset`.
- **Application Lifespan**: Initialized heavy shared components (`IntegrationService`, `QAChain`, vector stores, embedders) once during FastAPI lifespan startup to avoid per-request reconstruction overhead.
- **Dependency Decoupling**: Removed `aiogram` dependency from `requirements.txt`, `setup.py`, and `pyproject.toml`. Made `BOT_TOKEN` optional in configuration.
- **Entry Points**: Migrated `main.py` and `ragbot/main.py` to start the Uvicorn ASGI server with configurable `--host`, `--port`, `--workers`, and `--reload` parameters.
- **API Test Suite**: Implemented comprehensive test suites in `tests/api/test_api.py` covering application lifecycles, health checks, query execution, document uploads, and security validations.

## 2025-02-14 — Legacy Telegram Bot Improvements

- Implemented Anthropic API health check in `_check_anthropic_api()` (`outputs/health.py`).
- Fixed bare `except` in `app/ui/manager.py`: now catches `(KeyError, ValueError)` for text formatting.
- Added `admin_users` and `admin_users_list` to settings for configurable admin IDs via `ADMIN_USERS` env.
- Replaced hardcoded admin IDs in admin handlers with `settings.admin_users_list`.
- Fixed bug in `split_long_message`: `else` was incorrectly bound to `for` instead of inner `if`.
- Added comprehensive E2E test suite: `tests/e2e/test_project_e2e_complete.py`.
