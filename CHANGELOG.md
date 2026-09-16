# Changelog

## 2025-02-14

- Implemented Anthropic API health check in `_check_anthropic_api()` (outputs/health.py). Previously a placeholder.
- Fixed bare `except` in app/ui/manager.py: now catches `(KeyError, ValueError)` for text formatting.
- Added `admin_users` and `admin_users_list` to settings for configurable admin IDs via `ADMIN_USERS` env.
- Replaced hardcoded admin IDs in admin.py and ui_manager with settings.admin_users_list.
- Fixed bug in split_long_message: `else` was incorrectly bound to `for` instead of inner `if`.
- Added comprehensive E2E test suite: `tests/e2e/test_project_e2e_complete.py` covering Integration Service, Vector Store (FAISS), Query Aggregator, Advanced Filter, RAG pipeline, Health Check, and Analytics.
