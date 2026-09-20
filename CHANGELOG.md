# Changelog

All notable changes to the RAGBot project are documented in this file.

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
