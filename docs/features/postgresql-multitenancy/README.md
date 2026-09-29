# Phase 5 PostgreSQL Multi-Tenancy Operations

## Purpose

PostgreSQL is the authoritative persistence layer for TenantRAG multi-tenant metadata. Runtime tenant state must not fall back to SQLite or process-local dictionaries.

The Phase 5 schema contains:

- `tenants`
- `tenant_users`
- `tenant_api_keys`
- `tenant_quotas`
- `tenant_usage`
- `tenant_audit_logs`
- `tenant_sessions`

SQLAlchemy 2.x async sessions use `asyncpg`. Alembic is the only supported schema-management path. Application startup must not call `create_all()` or create tenant tables dynamically.

## Database roles

Use separate credentials for schema migration and application runtime.

### Migration owner

The migration owner creates and owns the schema objects and executes:

```bash
DATABASE_URL=postgresql+asyncpg://tenantrag_owner:<password>@localhost:5432/tenantrag \
  python -m alembic upgrade head
```

Do not use migration-owner credentials as the long-running application `DATABASE_URL`.

### Runtime role

The application role must be a non-owner role with no PostgreSQL privilege that bypasses RLS:

```sql
CREATE ROLE tenantrag_app
    LOGIN
    PASSWORD '<strong-password>'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOBYPASSRLS;

GRANT CONNECT ON DATABASE tenantrag TO tenantrag_app;
GRANT USAGE ON SCHEMA public TO tenantrag_app;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA public TO tenantrag_app;
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public TO tenantrag_app;
GRANT EXECUTE ON FUNCTION public.lookup_api_key_auth(text) TO tenantrag_app;
GRANT EXECUTE ON FUNCTION public.lookup_session_auth(text) TO tenantrag_app;
```

The migration owner should also configure equivalent default privileges for future tables and sequences if subsequent migrations create additional objects.

The runtime application URL then uses that role:

```env
DATABASE_URL=postgresql+asyncpg://tenantrag_app:<password>@localhost:5432/tenantrag
```

## RLS model

Every tenant table has Row-Level Security enabled. Normal operations set transaction-local PostgreSQL settings:

- `app.tenant_id` for tenant-scoped work
- `app.is_system_admin` for explicitly authorized cross-tenant system work

Policies enforce both row visibility and `WITH CHECK` writes.

The runtime role must remain a non-owner with `NOBYPASSRLS`. Superuser or `BYPASSRLS` credentials invalidate the isolation assumptions.

`tenant_api_keys` and `tenant_sessions` use narrowly scoped `SECURITY DEFINER` lookup functions to bootstrap tenant identity before normal RLS-scoped queries. Public execution is revoked. Grant only those functions to the runtime role.

## Fresh deployment

1. Create the PostgreSQL database and the migration-owner/runtime roles.
2. Run Alembic with the migration-owner URL:

   ```bash
   DATABASE_URL=postgresql+asyncpg://tenantrag_owner:<password>@localhost:5432/tenantrag \
     python -m alembic upgrade head
   ```

3. Apply runtime grants after migration.
4. Set the application `DATABASE_URL` to the runtime-role URL.
5. Start TenantRAG.
6. Run the PostgreSQL verification gate against a disposable verification database:

   ```bash
   TEST_DATABASE_URL=postgresql+asyncpg://postgres:<password>@localhost:5432/tenantrag_test \
     make verify-postgres
   ```

The dedicated CI job runs the same Alembic/RLS/auth checks against PostgreSQL 17.

## Legacy SQLite migration

The migration is offline. Do not dual-write SQLite and PostgreSQL.

### Dry run

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --source data/tenants/tenants.db \
  --source-timezone Asia/Tehran \
  --dry-run
```

`--source-timezone` is mandatory whenever the legacy database contains naive timestamps. The migrator will not silently guess a timezone.

### Cutover

1. Stop writes to the old service.
2. Back up the legacy SQLite database.
3. Run the dry-run and resolve every reported validation error.
4. Upgrade the PostgreSQL target to Alembic head.
5. Ensure the target tenant tables are empty.
6. Run:

   ```bash
   python scripts/migrate_sqlite_to_postgres.py \
     --source data/tenants/tenants.db \
     --source-timezone Asia/Tehran \
     --target-url postgresql+asyncpg://tenantrag_owner:<password>@localhost:5432/tenantrag
   ```

7. Apply/verify runtime grants.
8. Start the application with the runtime-role `DATABASE_URL`.
9. Run tenant/auth smoke tests and the PostgreSQL verification gate.

The migrator writes all tenant rows in one PostgreSQL transaction and verifies table counts before commit. A failure rolls the transaction back.

## Migration limitations

- Existing API-key hashes are copied verbatim. Raw API-key secrets are never reconstructed or logged.
- Legacy audit rows did not persist `user_id`, `success`, `error_message`, `ip_address`, or `user_agent`; those unknown values remain `NULL`.
- The historical runtime did not persist every usage update, so legacy `tenant_usage` can be incomplete. The migrator reports this limitation instead of inventing data.
- Historical user sessions lived only in process memory and cannot be migrated. All users must authenticate again after cutover.
- The old SQLite file is a migration source only. It is not a supported runtime fallback after Phase 5.

## Transaction rules

- One `AsyncSession` per business operation/task.
- Repositories do not own `commit()`.
- Mutations and their audit rows share the same database transaction where atomicity is required.
- Password/API-key hashing happens outside long database transactions.
- LLM, embedding, vector-store, HTTP, Redis, and other external I/O must not be held inside a PostgreSQL transaction.
- Quota reservations are atomic and short-lived; failed external work uses explicit compensation rather than holding locks during RAG execution.

## Verification checklist

Before merging or deploying Phase 5 changes:

```bash
make verify-tests
make verify-security
make verify-static
make verify-postgres
make verify-deps
```

The container gate additionally requires Docker:

```bash
make verify-container
```

CI treats PostgreSQL Verification, Ruff, MyPy, Bandit, dependency audit, the full test matrix, the security regression matrix, and container verification as blocking checks.
