# Baseline Audit and Verification Report

Phase 1 of production hardening. This is an audit and measurement phase only.
No source code, configuration, or existing documentation was changed. The only
files added are this report and `scripts/verify_baseline.sh`.

| Item | Value |
|---|---|
| Repository | `dibbed/tenant-rag` |
| Branch | `main` |
| Baseline commit | `606c479e8f96ebf5e3b7895f3bb7d1ecabe8ff53` ("fix(ci): align pydantic dependencies and harden test mocks across Python versions") |
| Audit date | 2026-09-26 |
| Method | Static review of source, configuration, scripts, and docs. GitHub Actions run history, job steps, annotations, and job logs for commits `606c479` and `ae51cf3`. |

## How to Read This Report

**Execution limitation.** The audit environment had read access to the
repository and to GitHub Actions results, but it did not have a shell. The
auditor could not run Python, pytest, Ruff, MyPy, Bandit, or Docker directly.
Every result below is labeled with its evidence source:

- **CI**: taken from GitHub Actions status, step results, or job logs.
- **Static**: derived from reading code, configuration, or scripts.
- **Not run**: no execution evidence exists yet. Run
  `bash scripts/verify_baseline.sh --install` to produce it, then record the
  numbers in this file.

Claims in `README.md`, `CHANGELOG.md`, and `SECURITY.md` were not accepted as
fact. Where they differ from the code, the difference is listed under
[Known Technical Risks Found](#known-technical-risks-found).

---

## Current State Summary

### What the project currently does

TenantRAG is a Python FastAPI service for Retrieval-Augmented Generation (RAG).
Clients ingest content (file upload, raw text, or a URL). The service loads,
chunks, and embeds the content, stores vectors in a vector store, and answers
questions with an LLM, returning sources and a confidence score. An optional
multi-tenant mode adds API key authentication and per-tenant storage
partitions.

The project was a Telegram bot before the migration ("RAG Telegram
Assistant"). `CHANGELOG.md` records the move to FastAPI on 2026-09-18.
Telegram-era remnants still exist (settings docstring, optional `bot_token`
setting, validation scripts, Prometheus job names).

### Repository structure (verified)

| Path | Contents |
|---|---|
| `ragbot/` | Application package (about 170 Python modules) |
| `ragbot/api/` | FastAPI app factory, routes (`health`, `query`, `documents`), dependencies (auth/tenant), rate-limit middleware, schemas |
| `ragbot/services/` | `IntegrationService`, `RAGService` (3,074 lines), `DocumentService`, graceful degradation |
| `ragbot/rag/` | Loaders, chunkers, embeddings, vector stores, retrieval, QA chain, query tools |
| `ragbot/multi_tenant/` | `TenantManager` (SQLite persistence), `TenantAuth`, tenant analytics, models |
| `ragbot/caching/` | Memory cache, Redis cache, semantic cache, cache manager |
| `ragbot/security/` | Encryption, key manager, backup, content/spam/toxicity filters |
| `ragbot/plugins/` | Plugin manager, loader, validator, registry, marketplace, examples |
| `ragbot/outputs/`, `ragbot/monitoring/`, `ragbot/analytics/` | Logging, metrics, health, monitoring, analytics |
| `ragbot/configs/` | Pydantic settings (2,457 lines), setup, migrate, validator |
| `tests/` | 46 test modules plus `conftest.py` |
| `benchmarks/`, `examples/` | Benchmark and example scripts |
| `scripts/` | Shell and Python operations scripts |
| `monitoring/` | Prometheus, Alertmanager, Loki, Grafana configuration and a separate compose file |
| Root | `main.py`, `Dockerfile`, `docker-compose.yml`, `Makefile`, `pyproject.toml`, `requirements*.txt`, `env.example`, `.env.test`, docs, two `.docx` guides |

### Application entry points

| Entry point | Target | Evidence |
|---|---|---|
| `python main.py` | `ragbot.main:main`, which runs `uvicorn.run("ragbot.api.app:app")` with `--host`, `--port`, `--reload`, `--workers` (env `HOST`, `PORT`, `RELOAD`, `WORKERS`) | `main.py`, `ragbot/main.py` |
| ASGI app | `ragbot.api.app:app` (created by `create_app()`) | `ragbot/api/app.py` |
| Console script `ragbot` | `ragbot.main:main` | `pyproject.toml [project.scripts]` |
| Console scripts `tenantrag`, `tenant-rag`, `ragbot-cli` | `ragbot.cli:main` (tenant, key, ingest, query, migrate, plugin, analytics commands) | `pyproject.toml`, `ragbot/cli.py` |
| Console scripts `ragbot-setup`, `ragbot-migrate` | `ragbot.configs.setup:main`, `ragbot.configs.migrate:main` | `pyproject.toml` |
| Docker | `CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]` | `Dockerfile` |
| Other root scripts | `run_e2e_tests.py`, `setup_monitoring.py`, `metrics_viewer.py` (a second copy exists in `monitoring/`) | tree |

HTTP routes registered in `ragbot/api/routes/__init__.py`:

| Method | Path | Auth dependency |
|---|---|---|
| GET | `/health`, `/api/v1/health` | None |
| POST | `/api/v1/query` | `get_tenant_context` |
| POST | `/api/v1/documents/upload` | `get_tenant_context` |
| POST | `/api/v1/documents/text` | `get_tenant_context` |
| POST | `/api/v1/documents/url` | `get_tenant_context` |
| POST | `/api/v1/documents/reset` | `get_tenant_context` and `verify_reset_authorization` |

There are no HTTP endpoints for tenant, user, or API key management. These
operations exist only in the CLI.

### Backend architecture overview

```
Client
  -> CORSMiddleware (allow_origins=*, allow_credentials=True)
  -> RateLimitMiddleware (in-memory sliding window, per process)
  -> FastAPI router (/health, /api/v1/...)
       -> dependencies: get_current_principal -> get_authorized_tenant_context
  -> IntegrationService (created once in lifespan)
  -> RAGService
       -> loaders -> chunker -> embedder -> vector store (per tenant when multi-tenant)
       -> semantic cache (tenant-keyed) -> retriever -> QA chain -> LLM provider
       -> TenantManager / TenantAuth (SQLite), PluginManager (in-process hooks)
```

The lifespan hook (`ragbot/api/app.py`) initializes `IntegrationService` and
`RAGService` once. If initialization fails, the app still starts with
`rag_service = None`, and routes that need it return HTTP 503. A global
exception handler returns a generic HTTP 500 body.

### Storage layer

- **Tenant data**: stdlib `sqlite3`, one shared connection with
  `check_same_thread=False`, file `data/tenants/tenants.db` (or
  `MULTI_TENANT_DATA_DIR/tenants.db`). Tables: `tenants`, `tenant_users`,
  `tenant_usage`, `tenant_audit_logs`, `tenant_api_keys` (indexes on
  `key_hash` and `tenant_id`). Tenants and users are also loaded into
  in-memory dicts at startup. (`ragbot/multi_tenant/tenant_manager.py`)
- **Vectors**: filesystem (FAISS, Chroma persist directory, Qdrant local path)
  or a remote Qdrant URL. Default `STORE_PATH` is `./data/vector_store`.
- **Cache**: in-memory L1, optional Redis L2 (`ENABLE_REDIS`), semantic cache.
- **Sessions and in-memory key cache**: `TenantAuth.user_sessions` and
  `TenantAuth.api_keys` are process-local dicts.
- `SQLAlchemy` and `alembic` are declared dependencies, but no module under
  `ragbot/` imports them.

### Vector database integrations

`ragbot/rag/store/factory.py` (`VectorStoreFactory`) registers three backends:

| Key | Class | Module |
|---|---|---|
| `faiss` (default, `VECTOR_DB=faiss`) | `FAISSVectorStore` (and subclass `FAISSStore`) | `faiss_store.py` |
| `chroma` / `chromadb` | `ChromaVectorStore` | `chroma_store.py` |
| `qdrant` | `QdrantVectorStore` | `qdrant_store.py` |

`create_store()` checks dependencies and falls back to a FAISS store when a
backend is missing, fails to import, or raises during construction. All
stores are wrapped in `AwaitableStoreProxy`. Migration tooling exists in
`ragbot/utils/vector_store_migration.py` and the CLI `migrate` command.

### Authentication and authorization flow

Source: `ragbot/api/dependencies.py`, `ragbot/multi_tenant/tenant_auth.py`.

1. If `settings.multi_tenant.enabled` is false (the code default), no
   authentication runs. `get_current_principal()` and
   `get_authorized_tenant_context()` return `None`.
2. In multi-tenant mode, the credential comes from `X-API-Key`, or from
   `Authorization: Bearer <token>`, or from a bare one-part `Authorization`
   value. A missing credential returns HTTP 401.
3. `TenantAuth.authenticate_principal()` first checks in-memory sessions, then
   API keys. API keys are looked up by `sha256(key)` in SQLite (active keys
   only), then by the raw value, then in the in-memory dict. Expiry, active
   flag, tenant existence, and `api_access` permission are checked.
4. The principal's tenant is compared to `X-Tenant-ID`. A mismatch returns
   HTTP 403 unless the principal is super admin. The target tenant must exist
   and be active.
5. Reset requires role `admin`, `super_admin`, or `manager`, or permission
   `delete_documents` or `manage_tenant`, or super admin.
6. Keys are generated as `rgb_<secrets.token_urlsafe(32)>`. User passwords use
   PBKDF2-HMAC-SHA256 with 100,000 iterations and a random salt.

### Tenant isolation mechanisms

- **Vector stores**: `RAGService.get_vector_store(tenant_id)` creates and
  caches one store per tenant. FAISS uses `<STORE_PATH>/tenants/<tenant_id>`.
  Chroma and Qdrant use collection `tenant_<tenant_id>`. The store classes
  themselves do not filter by tenant (no `tenant_id` references in
  `ragbot/rag/store/`), so isolation depends entirely on path or collection
  separation.
- **Retrievers**: one `AdvancedRetriever` per tenant.
- **Semantic cache**: entries carry `tenant_id`; cache keys are prefixed with
  the tenant id; lookups skip entries of other tenants.
- **Limits and status**: `RAGService` checks tenant status and
  `check_tenant_limits()` before ingest and query.
- **Reset**: tenant reset deletes `<STORE_PATH>/tenants/<tenant_id>` and clears
  that tenant's semantic cache. Global reset (no tenant) clears everything.

### Testing setup

- Framework: pytest 8.4.2, pytest-asyncio (`asyncio_mode = "auto"`),
  pytest-cov, pytest-mock, hypothesis.
- `pyproject.toml` `addopts` always enable coverage (`--cov=ragbot`, term,
  HTML, XML) with `--strict-markers --strict-config`.
- `tests/conftest.py` forces CPU (`CUDA_VISIBLE_DEVICES=""`,
  `TORCH_DEVICE=cpu`), `TESTING=true`, in-memory SQLite URL, Redis off.
- Test modules: 29 unit, 11 integration, 3 e2e, 2 api, 1 security (46 total).
- Conditional skips exist for Chroma, Qdrant, and FAISS availability; one
  unconditional skip ("Requires OpenAI API key") in
  `tests/integration/test_phase4_quality_integration.py`.
- Heavy use of mocks for embedders, LLMs, Redis, and HTTP.

### CI/CD setup

- One workflow: `.github/workflows/ci.yml`, on push and pull request to
  `main`/`master`.
- Matrix: Python 3.10, 3.11, 3.12 on `ubuntu-latest`, `fail-fast: false`.
- Steps: checkout, setup-python with pip cache,
  `pip install -r requirements.txt`, `pip install -e ".[dev]"`, `pytest -v`.
- No lint, format, type-check, security scan, coverage threshold, Docker build,
  artifact upload, or deployment job.

### Docker and deployment setup

- `Dockerfile`: single stage, `python:3.11-slim`, installs `build-essential`,
  `git`, `curl`, installs `requirements.txt`, copies the repository, runs as
  non-root `appuser` (uid 10001), exposes 8000, `HEALTHCHECK` on
  `/api/v1/health`.
- `docker-compose.yml`: one service `tenant-rag`, `env_file: .env`, port 8000,
  bind mounts `./data`, `./logs`, `./cache`, healthcheck. No Redis, Qdrant, or
  monitoring services.
- `monitoring/docker-compose.yml` and `monitoring/*.yml`: separate Prometheus,
  Grafana, Loki, Alertmanager setup.
- `scripts/deploy.sh`: wraps `docker-compose` with per-environment override
  files.
- `Makefile`: `setup`, `test`, `lint`, `format`, `type-check`, `security`,
  `build`, `build-dev`, `docker-compose-up`, and others.

---

## Verification Results

| Check | Status | Details |
|---|---|---|
| Python version | CI: verified | CI matrix 3.10, 3.11, 3.12. Job logs show CPython 3.11.16 and 3.12.14. The 3.10 patch version was not captured. Docker image uses `python:3.11-slim`. `requires-python >=3.10`. |
| Dependency installation | CI: pass on `606c479` | "Install dependencies" step succeeded on all three versions. Previous commit `ae51cf3` failed this step on 3.12. No lock file; unpinned packages resolved to chromadb 1.5.9, qdrant-client 1.19.1, pydantic 2.13.5 in the 3.11 job. |
| Tests | CI: pass on `606c479` | `pytest -v` succeeded on 3.10, 3.11, 3.12 (run 36146738520). Pass/skip counts could not be read from accessible CI output. README claim "627 passed, 1 skipped" is not independently verified. Previous commit `ae51cf3` failed the test step on 3.10 (run 36145575750). |
| Coverage | Partial (CI generates, value not captured) | Coverage runs on every pytest call via `addopts`, but CI does not upload or enforce it. The omit list excludes most core modules (see C17), so the number, when measured, does not represent core RAG or tenant code. |
| Lint | Not run | Ruff 0.12.12 is configured in `pyproject.toml` but not run in CI. Violation count unknown. Config uses deprecated top-level sections (see C22). |
| Formatting | Not run | `ruff format` is configured. No check-only target exists; `make format` rewrites files. |
| Type checking | Not run | MyPy 1.10.1 with strict options in `pyproject.toml`. Not in CI. `make lint` hides MyPy failures with `|| true`. Error count unknown. |
| Security scan | Not run | Bandit 1.7.9 is a dev dependency and in `make security`. Not in CI. |
| Docker build | Not run | No CI job builds the image. Static review found no syntax problem in `Dockerfile`. `make build-dev` targets a stage that does not exist (see C20). |
| Docker compose validation | Not run | `docker-compose.yml` requires a `.env` file that is not in the repository, so `docker compose config` fails on a clean checkout until `.env` exists. |
| Deployment checks | Static: fail | `scripts/deploy.sh` references `docker-compose.dev.yml`, `docker-compose.prod.yml`, and `.env.example`, which do not exist. `scripts/validate_system.sh` and `scripts/run_final_validation.sh` reference removed or missing modules, test folders, and env files (see C21, C26). |

### Commands

Commands executed by GitHub Actions for the baseline commit (evidence: run
36146738520, jobs "Test (Python 3.10/3.11/3.12)"):

| Command | Result | Summary |
|---|---|---|
| `python -m pip install --upgrade pip` | Pass | pip 26.2.1 already present |
| `pip install -r requirements.txt` | Pass | About 4.07 GB pip cache restored (torch, transformers, chromadb, qdrant-client and others) |
| `pip install -e ".[dev]"` | Pass | |
| `pytest -v` (env `CUDA_VISIBLE_DEVICES=""`, `TORCH_DEVICE=cpu`) | Pass | About 2 minutes per Python version |

CI annotations on the runs:

- Warning: Node.js 20 is deprecated; `actions/checkout@v4` and
  `actions/setup-python@v5` are forced to run on Node.js 24.
- Notice: the `ubuntu-latest` label migrates to Ubuntu 26 from
  October 19, 2026.

Commands defined in `scripts/verify_baseline.sh`, not yet executed for this
baseline:

| Command | Purpose |
|---|---|
| `python3 --version` | Record interpreter |
| `python3 -m pip install --upgrade pip && python3 -m pip install -r requirements.txt && python3 -m pip install -e ".[dev]"` | Same install as CI (only with `--install`) |
| `python3 -m pip check` | Dependency consistency |
| `python3 -m pytest -q -rs --junitxml=<out>/junit.xml` | Tests; coverage comes from `addopts` |
| read `coverage.xml` `line-rate` | Coverage percentage |
| `python3 -m ruff check . --no-fix --statistics` | Lint (no changes to files) |
| `python3 -m ruff format --check .` | Formatting (no changes to files) |
| `python3 -m mypy ragbot --ignore-missing-imports` | Type checking, same as `make type-check` |
| `python3 -m bandit -q -r ragbot` | Security scan, same scope as `make security` |
| `bash -n scripts/*.sh` | Shell syntax |
| `docker build -t tenant-rag:baseline .` | Docker build |
| `docker compose -f docker-compose.yml config -q` | Compose validation |

---

## Known Technical Risks Found

Severity is the auditor's estimate for production use: High, Medium, Low.

### Confirmed issues

Each item below is verified from code, configuration, or CI evidence.

#### Security and tenant isolation

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| C1 | High | Tenant store creation fails open to the shared store. If creating a tenant store raises, `get_vector_store()` returns the global `self.vector_store`. If creating a tenant retriever raises, `get_retriever()` returns the global `advanced_retriever`. Tenant data can then be written to or read from the shared store. | `ragbot/services/rag_service.py`, `get_vector_store()`, `get_retriever()` |
| C2 | High | The factory fallback ignores the tenant partition. `create_store()` falls back to FAISS on missing dependency, import error, or any constructor exception. `_create_fallback_store()` sets `path=settings.store_path` when no `path`/`store_path` is given. Tenant kwargs for Chroma have only `persist_directory` and `collection_name`, and Qdrant kwargs carry the shared Qdrant `path`. All tenants then share one fallback path. | `ragbot/rag/store/factory.py`, `create_store()`, `_create_fallback_store()`; `rag_service.py` tenant kwargs |
| C3 | High | A stored key hash works as a credential. After the hash lookup fails, the code looks up the raw credential as if it were a hash (`get_api_key_by_hash(api_key)`). A caller who presents the stored SHA-256 hex value is authenticated. Anyone with read access to `tenants.db` or its backups can use keys without the secret. | `tenant_auth.py`, `authenticate_api_key()` and `authenticate_principal()` |
| C4 | High | Any API key with the `manage_tenant` permission becomes super admin. `authenticate_principal()` sets `is_super_admin=True` from that permission, and super admin skips the `X-Tenant-ID` boundary check. `create_api_key()` accepts a caller-supplied `permissions` list. | `tenant_auth.py`, `authenticate_principal()`, `create_api_key()`; `dependencies.py`, `get_authorized_tenant_context()` |
| C5 | High | No authentication when multi-tenant mode is off, and it is off by default. `MultiTenantSettings.enabled` defaults to `False`. All routes, including `POST /api/v1/documents/reset` (clears the vector store and all caches), are then open. `env.example` sets `MULTI_TENANT_ENABLED=true`, but the code default is open. | `ragbot/configs/settings.py` `MultiTenantSettings`; `dependencies.py` |
| C6 | High | Server-side request forgery (SSRF) in URL ingestion. `/api/v1/documents/url` accepts any `http(s)` URL. The loader fetches it with aiohttp and follows redirects, with no host or IP restriction. The content is indexed and can be read back through `/api/v1/query`. | `ragbot/api/routes/documents.py` `ingest_url()`; `ragbot/rag/loaders/url.py` |
| C7 | Medium | Tenant verification fails open. In `get_authorized_tenant_context()`, any non-HTTP exception from `get_tenant()` is logged at debug level and the request continues. | `ragbot/api/dependencies.py` |
| C8 | Medium | Test-double logic in the production auth path. `dependencies.py` imports `unittest.mock.MagicMock` and changes authorization behavior when the tenant manager or tenant status is a `MagicMock`. | `ragbot/api/dependencies.py` |
| C9 | Medium | The rate limiter trusts `X-Forwarded-For` without a trusted-proxy list, so clients can bypass limits by changing the header. `_client_records` never deletes client keys, so spoofed values grow memory without bound. Limits are per process, so `WORKERS>1` multiplies the effective limit. | `ragbot/api/middleware/rate_limit.py` |
| C10 | Medium | CORS allows any origin with credentials (`allow_origins=["*"]`, `allow_credentials=True`, all methods and headers). | `ragbot/api/app.py` `create_app()` |
| C11 | Medium | Upload reads the full file into memory before the size check (`await file.read()`, default limit 50 MB). Large bodies consume memory before rejection. | `documents.py` `upload_document()` |
| C12 | Medium | Tenant IDs are not format-validated anywhere in `ragbot/multi_tenant/` or the CLI. The id is joined into filesystem paths and passed to `shutil.rmtree()` during tenant reset. The current guard is the tenant existence check, which fails open (C7). | `rag_service.py` `get_vector_store()`, `reset_store()` |
| C13 | Low | The health endpoint has no auth and returns exception text in `issues` and component details. | `ragbot/api/routes/health.py` |
| C14 | Low | Raw API keys are kept as dict keys in `TenantAuth.api_keys`. Sessions exist only in process memory and do not survive restart or span workers. | `tenant_auth.py` |
| C15 | Low | API actions are tracked with a fixed `user_id="api_user"`, not the authenticated principal. No per-principal audit record of ingest, query, or reset exists in the API layer. | `documents.py`, `query.py` |

#### Verification tooling and CI

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| C16 | Medium | CI runs only pytest. No lint, format, type, security, coverage gate, or Docker build. | `.github/workflows/ci.yml` |
| C17 | Medium | Coverage excludes most core code: `ragbot/services/*` (includes `RAGService`), `ragbot/caching/*` (semantic cache), `ragbot/outputs/*`, `ragbot/rag/embeddings/*`, `ragbot/rag/qa/*`, `ragbot/rag/store/faiss_store.py` (default store), `ragbot/configs/settings.py`, and several loaders. | `pyproject.toml` `[tool.coverage.run] omit` |
| C18 | Medium | Pytest hides "coroutine was never awaited" warnings, which can mask real async bugs. | `pyproject.toml` `filterwarnings` |
| C19 | Low | `make lint` hides MyPy failures (`|| true`). `make format` rewrites files; no check-only format target exists. | `Makefile` |
| C20 | Low | Broken Makefile targets: `build-dev` uses `--target development`, but the Dockerfile has no stages. `create-env` copies `.env.example`, but the repo file is `env.example`. | `Makefile`, `Dockerfile` |
| C21 | Medium | Existing validation scripts do not work against the current tree. `validate_system.sh` imports `ragbot.app.bot` (removed per CHANGELOG 2026-09-20), runs `tests/performance/`, and requires `.env.example`, `.env.development`, `.env.production`, `.env.testing`, `docs/CONFIGURATION.fa.md`, `docs/TESTING.fa.md`, none of which exist. `run_final_validation.sh` runs `tests/final_validation/*` (missing). It also uses `((PASSED_TESTS++))` under `set -e`; the first increment from 0 returns status 1 and stops the script. | `scripts/validate_system.sh`, `scripts/run_final_validation.sh` |
| C22 | Low | Ruff config uses deprecated top-level `select`/`ignore` and `[tool.ruff.isort]`. Current Ruff expects these under `[tool.ruff.lint]` and prints deprecation warnings. | `pyproject.toml` |
| C23 | Medium | Builds are not reproducible. There is no lock file. `requirements.txt` has unpinned `chromadb>=0.5.0`, `qdrant-client>=1.9.0`, and pydantic ranges. `requirements.txt` and `pyproject.toml` list different dependency sets. The run before the baseline failed on dependency resolution (3.12) and tests (3.10). | `requirements.txt`, `pyproject.toml`, CI run 36145575750 |
| C24 | Low | CI uses actions that target deprecated Node.js 20 and the floating `ubuntu-latest` label, which moves to Ubuntu 26 from October 19, 2026. | CI annotations |

#### Deployment and packaging

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| C25 | Medium | The production image installs dev, test, and docs tools (pytest, mypy, ruff, pre-commit, bandit, mkdocs), because `requirements.txt` contains them. The image is single-stage, so `build-essential` and `git` stay in the runtime image. | `Dockerfile`, `requirements.txt` |
| C26 | Medium | `scripts/deploy.sh` needs `docker-compose.dev.yml`, `docker-compose.prod.yml`, and `.env.example`, which do not exist. It also requires the v1 `docker-compose` binary. | `scripts/deploy.sh` |
| C27 | Low | `docker-compose.yml` requires `.env`, which is not committed. The `version: '3.8'` key is obsolete in Compose v2. The compose file has no Redis, but `env.example` sets `ENABLE_REDIS=true` with `REDIS_URL=redis://localhost:6379/0`, which does not reach a Redis server from inside the container. | `docker-compose.yml`, `env.example` |
| C28 | Low | Monitoring config drift: `monitoring/prometheus.yml` scrapes `ragbot:8080`, but the compose service is `tenant-rag` and exposes only port 8000. | `monitoring/prometheus.yml`, `docker-compose.yml` |
| C29 | Low | `SQLAlchemy` and `alembic` are required dependencies but are not imported under `ragbot/`. | `requirements.txt`, `pyproject.toml`, source search |
| C30 | Low | `.env.test` is committed even though `.gitignore` excludes `.env.*`. Its values are fake placeholders. | tree, `.gitignore` |

#### Documentation drift (claims that the code does not support)

| ID | Claim | Source of claim | What the code does |
|---|---|---|---|
| D1 | "Salted SHA-256" API keys, compared with `secrets.compare_digest` | README | Unsalted `hashlib.sha256(key).hexdigest()` with SQL equality lookup. `compare_digest` is used only in `ragbot/security/encryption.py`. |
| D2 | SQLite uses WAL journal mode | README, CHANGELOG 2026-09-22 | No `journal_mode` or WAL pragma exists under `ragbot/`. |
| D3 | Tenant indexes live in `data/vector_stores/<tenant_id>/` | README | Path is `<STORE_PATH>/tenants/<tenant_id>`; default `STORE_PATH` is `./data/vector_store`. |
| D4 | Reset requires `admin` or `super_admin` | CHANGELOG 2026-09-24 | Also allows role `manager` and any principal with `delete_documents` or `manage_tenant`. |
| D5 | "627 passed, 1 skipped, 0 failed" | README badge and text, CHANGELOG | Not verified. CI is green on the baseline commit, but counts were not visible. |
| D6 | API-first service | README | Telegram-era names remain in settings, scripts, and monitoring config. |

### Possible risks requiring deeper investigation

These are plausible from the code but were not proven in this audit.

| ID | Risk | Why it needs investigation |
|---|---|---|
| P1 | A revoked key may still work in a long-running process. The SQLite lookup filters `is_active = 1`. On a miss, the code falls back to the in-memory `api_keys` dict, which has no revocation check. A CLI revocation in another process does not clear the server's dict. | Needs a test that creates a key in-process, revokes it from another process, then calls the API. |
| P2 | One shared SQLite connection is used from async code, and multiple uvicorn workers open the same file without WAL. | Behavior under concurrent writes (usage counters, audit logs, `last_used_at`) is unmeasured. |
| P3 | The query path checks tenant status with both an enum comparison and `str(status).lower() != "active"`. On Python 3.11+, `str()` of a `str`-Enum member returns `TenantStatus.ACTIVE`. The check is correct only while models keep `use_enum_values=True`. | Could reject active tenants if a code path passes an enum instance. |
| P4 | Chroma and Qdrant can reject collection names such as `tenant_<id>` for some ids. With C1 and C2, a rejection falls back to a shared store. | Needs tests with edge-case tenant ids on each backend. |
| P5 | MyPy is configured strict (`disallow_untyped_defs` and others), and many functions are untyped. | A large error count is likely. Measure it before any type work. |
| P6 | Ruff violation count is unknown. | Measure it before enabling lint in CI. |
| P7 | Docker image build time and size are unknown. `torch==2.8.0` from default PyPI on Linux pulls CUDA wheels (CI pip cache is about 4 GB). The image installs `pytesseract` but not the `tesseract` binary. | Build the image and test OCR ingestion in the container. |
| P8 | `ragbot/outputs/metrics.py` can start a Prometheus HTTP server on `monitoring.metrics_port`. | Check whether it starts in API mode and whether it is exposed without auth. |
| P9 | The plugin system loads and runs in-process code and has a marketplace URL setting. | The trust model and sandboxing were not reviewed. |
| P10 | Tests use many mocks. It is not verified whether any test covers the fail-open paths in C1, C2, C3, C4, and C7. | Map tests to the auth and isolation code paths. |
| P11 | Data at rest is not encrypted (the README states this). `EncryptionManager` and `KeyManager` are created in `RAGService`. | Where keys are stored and what they protect were not reviewed. |

---

## Production Readiness Baseline

### What is working

- The test suite passes in CI on Python 3.10, 3.11, and 3.12 for the baseline
  commit.
- The FastAPI app starts through one path (`main.py` to uvicorn) with shared
  services created once in lifespan, a generic 500 handler, and 503 when core
  services are unavailable.
- Ingestion routes check file extension, empty content, and size; temporary
  files are removed in `finally` blocks; temp paths are removed from responses.
- Multi-tenant mode has a clear 401/403 split, hashed key storage with prefix,
  expiry and revocation flags, a tenant boundary check on `X-Tenant-ID`, and
  tenant status and quota checks.
- Per-tenant vector store partitions, a tenant-keyed semantic cache, and a
  tenant-scoped reset exist, and an isolation integration test covers the
  cache and FAISS partition cases.
- User passwords use salted PBKDF2-HMAC-SHA256 with 100,000 iterations.
- The container runs as a non-root user and has a health check.

### What is missing

- Lint, format, type, security, and Docker build checks in CI, and a coverage
  threshold that includes core modules.
- A dependency lock file and a single source of truth for dependencies.
- A separate runtime dependency set for the production image.
- Working deployment assets: the compose override files and env template that
  `deploy.sh` expects, and a committed `.env` template name that matches the
  scripts.
- SSRF protection for URL ingestion.
- Tenant id format validation.
- A trusted-proxy setting for client IPs and a shared (multi-worker) rate
  limiter.
- Shared session and key-cache state for multiple workers.
- A per-principal audit trail for API actions.
- HTTP management endpoints for tenants and keys (CLI only today; this may be
  intentional).

### What requires future hardening

1. Tenant isolation: remove all fallbacks to shared stores (C1, C2) and make
   tenant verification fail closed (C7).
2. Authentication: stop accepting stored hashes as credentials (C3), derive
   super admin from role only (C4), and decide the secure default for
   single-tenant mode (C5).
3. Remove test-double logic from production code (C8).
4. Network edge: SSRF guard (C6), rate limiter proxy trust and eviction (C9),
   explicit CORS origins (C10), streaming size limits (C11).
5. Verification: add lint, type, security, and Docker jobs to CI in report-only
   mode first; narrow the coverage omit list; stop hiding un-awaited coroutine
   warnings.
6. Supply chain: lock dependencies, split runtime and dev requirements, use a
   multi-stage image.
7. Deployment: fix or remove broken scripts and Makefile targets; align
   compose, env template, and monitoring names.
8. Documentation: correct README and CHANGELOG claims D1 to D6 after the code
   is fixed.

---

## Re-running This Baseline

```bash
# Mirror the CI install, then run every check (continues past failures)
bash scripts/verify_baseline.sh --install

# Checks only, using the current environment
bash scripts/verify_baseline.sh

# Skip Docker or the test suite
bash scripts/verify_baseline.sh --skip-docker --skip-tests
```

The script writes logs and a `summary.md` table to
`$TMPDIR/tenant-rag-baseline-<timestamp>/` (override with
`BASELINE_OUT_DIR`). It does not change tracked files. Pytest writes
`coverage.xml`, `htmlcov/`, and `data/` artifacts, which are already in
`.gitignore`. The script exits 1 if any check fails; skipped checks do not fail
the run.

After the first local run, replace every "Not run" entry in
[Verification Results](#verification-results) with the measured values
(test counts, coverage percentage, Ruff and MyPy counts, Docker result).
