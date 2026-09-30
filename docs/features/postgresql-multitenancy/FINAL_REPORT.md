# Phase 5 Final Completion Report

**Project:** TenantRAG  
**Phase:** Phase 5 — PostgreSQL Multi-Tenant Migration & Schema Unification  
**Completion date:** 2026-09-30  
**Verified implementation commit:** `2869f3e6ee1c628cd38a23db5e3b2c996f348173`

## Executive summary

Phase 5 replaces legacy multi-tenant runtime authority with PostgreSQL-backed persistence and moves schema management to Alembic. Tenant identity, users, API keys, sessions, quotas, usage, and audit data now have a relational PostgreSQL authority. The production `TenantManager` no longer selects SQLite as a runtime backend.

The phase also introduces PostgreSQL Row-Level Security (RLS), a non-owner runtime-role model, narrow `SECURITY DEFINER` bootstrap/system functions, offline SQLite-to-PostgreSQL migration tooling, real PostgreSQL CI verification, PostgreSQL local-development wiring, and operator documentation.

## Completed work

### Async PostgreSQL runtime

- SQLAlchemy 2.x async runtime using `asyncpg`.
- `DatabaseRuntime` owns the async engine and `async_sessionmaker`.
- PostgreSQL URL normalization rejects unsupported database backends for this runtime.
- Database runtime disposal is integrated with service shutdown.

### Relational tenant schema

Alembic manages the Phase 5 schema for:

- `tenants`
- `tenant_users`
- `tenant_api_keys`
- `tenant_quotas`
- `tenant_usage`
- `tenant_audit_logs`
- `tenant_sessions`

Current Alembic head: `phase5_0005`.

### Row-Level Security and runtime privilege boundary

- RLS is enabled on all tenant tables.
- RLS is forced on all tenant tables.
- Normal tenant work uses transaction-local `app.tenant_id`.
- The runtime application role is expected to be a non-owner with `NOSUPERUSER` and `NOBYPASSRLS`.
- Directly setting `app.is_system_admin=true` as the runtime role does not grant cross-tenant visibility.
- Cross-tenant system operations use narrow `SECURITY DEFINER` functions owned by the migration/table owner.
- Public execution is revoked from security-definer entrypoints.
- Auth bootstrap functions use a fixed safe `search_path`.

Supported narrow system/bootstrap functions include:

- `lookup_api_key_auth(text)`
- `lookup_session_auth(text)`
- `list_tenant_ids_admin(boolean)`
- `deactivate_expired_api_keys_admin(timestamptz)`
- `delete_expired_sessions_admin(timestamptz)`

### Authentication persistence

- Tenant users are PostgreSQL-backed.
- API keys persist only the existing password-style hash representation; raw API keys are returned once.
- Session raw tokens are never persisted; PostgreSQL stores SHA-256 token hashes.
- API-key bootstrap filters inactive/revoked keys.
- Session bootstrap filters revoked sessions.
- Login/session/API-key mutations remain transactionally coordinated with related audit writes where required.
- Multi-worker revocation behavior is verified by the PostgreSQL test gate.

### Transaction and repository model

- Repositories do not own `commit()` or `rollback()`.
- Business operations own transaction scope.
- User quota checks use row locking where required.
- Usage accounting uses PostgreSQL atomic upsert behavior.
- Parent tenant records are flushed before dependent quota rows where insert ordering requires it.
- External RAG/LLM/vector/network I/O is not intentionally held inside database transactions.

### Tenant runtime cleanup

- Production TenantManager runtime authority is PostgreSQL-only.
- Legacy SQLite runtime selection was removed.
- Process-local dictionaries are not the authoritative persistence layer for tenant runtime state.
- Legacy SQLite support remains only for migration/compatibility test fixtures where needed.

### SQLite to PostgreSQL migration

The offline migrator:

- opens the SQLite source read-only;
- validates required legacy tables;
- supports dry-run;
- requires explicit source timezone for naive timestamps;
- refuses a non-empty PostgreSQL target;
- runs target writes in a single transaction;
- preserves API-key hashes verbatim;
- preserves the source-local calendar date for legacy daily usage buckets while validating the declared source timezone;
- preserves unknown legacy audit outcomes as `NULL`/unknown rather than coercing them to success;
- does not invent missing legacy audit metadata;
- documents that historical in-memory sessions cannot be migrated;
- documents that historical usage may be incomplete;
- verifies target row counts before completion.

### CI and local operations

- A dedicated PostgreSQL CI job upgrades a clean PostgreSQL database to Alembic head and runs real RLS/auth verification.
- PostgreSQL 17 is used by the CI service.
- Local Docker Compose includes PostgreSQL for development.
- The verification summary treats PostgreSQL verification as blocking.
- Operational documentation covers owner/runtime roles, grants, migration, cutover, and verification.

## Verification results

### Local final verification on `2869f3e`

- Full test suite: **1116 passed, 0 failed, 0 errors, 34 skipped**.
- Security manifest: **358 collected, 358 present in the manifest**.
- Focused Phase 5 database/security tests: passing.
- Legacy migration tests: **8 passed**.
- Ruff blocking gate: **0 findings**.
- MyPy blocking gate: **0 errors**.
- Bandit blocking gate: **0 HIGH, 0 MEDIUM, 92 LOW**.
- `uv lock --check`: passed.
- `requirements.txt` matches the frozen `uv.lock` export.
- Locked default dependency environment: **132 packages audited, 0 blocking advisories**.
- Non-blocking default dependency advisories at verification time:
  - `markdown==3.6` — MODERATE
  - `python-dotenv==1.0.0` — MODERATE
  - `scikit-learn==1.4.2` — MODERATE

The local development/test environment contains additional optional/dev packages and is not the dependency gate used for production/default installation. The official blocking dependency check audits the locked default environment.

### GitHub Actions verification

Verification Pipeline run **#60** for commit `2869f3e` completed successfully.

Blocking jobs confirmed successful include:

- PostgreSQL Verification
- Tests — Python 3.10
- Tests — Python 3.11
- Tests — Python 3.12
- Security Regression Suite — Python 3.10
- Security Regression Suite — Python 3.11
- Security Regression Suite — Python 3.12
- Static Analysis — Ruff
- Static Analysis — MyPy
- Static Analysis — Bandit
- Dependency Vulnerability Check
- Container Build Check
- Verification Summary

Optional-extra audit jobs also completed successfully as report-only checks.

## Known limitations and operational notes

- Existing SQLite sessions cannot be migrated because the historical runtime kept them in process memory; users must authenticate again after cutover.
- Historical legacy usage can be incomplete because older runtime behavior did not persist every process-local usage update.
- Missing fields in legacy audit rows remain `NULL` rather than being fabricated.
- Production must use separate migration-owner and non-owner runtime credentials.
- Migration-owner credentials must not be used as the long-running application `DATABASE_URL`.
- The runtime role must remain non-owner, non-superuser, and `NOBYPASSRLS`.
- PostgreSQL schema changes must continue through Alembic rather than runtime `create_all()`.
- The default dependency gate is clean of blocking advisories, but moderate advisories remain as normal dependency-maintenance work.

## Phase 5 completion status

Phase 5 implementation, migration tooling, runtime cleanup, security hardening, documentation, PostgreSQL verification, dependency verification, and container verification are complete.

The remaining release action is the normal repository workflow: merge the verified Phase 5 pull request into `main`, then verify the resulting `main` workflow run.
