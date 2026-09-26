# 🧪 Testing & Verification Guide

This guide details the test philosophy, directory topology, and execution constraints for the RAGBot test suite.

---

## 1. Mandatory Hardware Safety & CPU Isolation Invariant

> [!CAUTION]
> **CRITICAL HARDWARE INVARIANT**: All test execution must be forced onto **CPU only**.
> Running PyTorch or FAISS tests with CUDA activated can trigger display driver freezes, system crashes, or out-of-memory errors on local development environments.

Before executing `pytest`, you **must** set the environment variables:

### Windows (PowerShell):
```powershell
$env:CUDA_VISIBLE_DEVICES = ""
$env:TORCH_DEVICE = "cpu"
.\venv\Scripts\pytest.exe -o addopts='' -q
```

### Linux / macOS:
```bash
export CUDA_VISIBLE_DEVICES=""
export TORCH_DEVICE="cpu"
pytest -o addopts='' -q
```

---

## 2. Test Suite Topology

The repository organizes tests into five clean, isolated directories under `tests/`:

```text
tests/
├── api/                  # FastAPI routes, lifecycle, rate limiting, and HTTP error handling
│   ├── test_api.py       # Lifespan, endpoints, validation, path traversal, error handling
│   └── test_rate_limit.py# In-memory sliding-window rate limiting middleware tests
├── unit/                 # Pure unit tests with mocked external I/O
│   ├── test_faiss_store.py      # Vector index operations, async concurrency lock
│   ├── test_semantic_cache.py   # Cosine similarity cache hits/misses, eviction
│   ├── test_chunkers.py         # Text chunking algorithms and boundary detection
│   ├── test_loaders.py          # PDF, DOCX, TXT, HTML parsers
│   ├── test_multi_tenant.py     # Tenant CRUD, SQLite persistence, quota enforcement
│   ├── test_cli_tenant_keys.py  # CLI tenant API key commands
│   └── test_validation.py       # Pydantic schema validation rules
├── integration/          # Multi-component integration tests
│   ├── test_api_tenant_plugin.py          # Multi-tenant and plugin API route integration
│   ├── test_multi_tenant_isolation.py     # Cross-tenant vector & cache partition checks
│   ├── test_phase4_quality_integration.py # QAChain with embedding & retrieval pipelines
│   └── test_migrate_faiss_to_qdrant.py    # Cross-store migration verification
├── security/             # Security, authentication, and authorization test suite
│   └── test_tenant_auth_security.py       # Impersonation, cross-tenant, reset RBAC, revocation
└── e2e/                  # End-to-end full system flows
    ├── test_project_e2e_complete.py       # Complete ingest-retrieve-answer flows
    └── test_security_workflows.py         # End-to-end security and rate limit validation
```

The Security Regression Suite (section 5) is `tests/security` together with the edge protection and tenant isolation tests that `tests/security/suite_manifest.json` lists. `tests/verification` tests the tools of the Verification Pipeline.

---

## 3. Targeted Test Execution Commands

### Run Full Repository Suite (Recommended for Pre-Commit Checks)
```powershell
$env:CUDA_VISIBLE_DEVICES = ""; $env:TORCH_DEVICE = "cpu"; .\venv\Scripts\pytest.exe -o addopts='' -q
```
*Current result* (Verification Pipeline, Python 3.10, 3.11 and 3.12): **1005 passed, 11 skipped, 0 failed**.

### Run Security & Multi-Tenant Authorization Tests
```powershell
$env:CUDA_VISIBLE_DEVICES = ""; $env:TORCH_DEVICE = "cpu"; .\venv\Scripts\pytest.exe -o addopts='' tests/security/ -v
```

### Run API Endpoints & Rate Limiter Tests Only
```powershell
$env:CUDA_VISIBLE_DEVICES = ""; $env:TORCH_DEVICE = "cpu"; .\venv\Scripts\pytest.exe -o addopts='' tests/api/ -v
```

### Run Vector Store Concurrency & FAISS Tests
```powershell
$env:CUDA_VISIBLE_DEVICES = ""; $env:TORCH_DEVICE = "cpu"; .\venv\Scripts\pytest.exe -o addopts='' tests/unit/test_faiss_store.py -v
```

### Run Semantic Cache Tests
```powershell
$env:CUDA_VISIBLE_DEVICES = ""; $env:TORCH_DEVICE = "cpu"; .\venv\Scripts\pytest.exe -o addopts='' tests/unit/test_semantic_cache.py -v
```

---

## 4. Test Fixtures & Mocking Policy

1. **Deterministic Test Data**:
   Tests generate deterministic synthetic vectors and mock LLM generation responses unless explicitly testing real local models (`sentence-transformers`).
2. **Network Isolation**:
   External API calls (e.g. OpenAI, Anthropic, OpenRouter) are patched with `unittest.mock.AsyncMock` in unit and API test suites to ensure offline repeatability and eliminate external latency.
3. **Temporary Filesystem Cleanup**:
   All upload and vector store disk operations utilize `pytest`'s `tmp_path` fixture or automated cleanup context managers to prevent leaving leftover test files in `./data/`.

---

## 5. Verification Pipeline

CI runs the Verification Pipeline (`.github/workflows/ci.yml`) on every pull request to `main` and every push to `main`. Details: `docs/features/security-verification-pipeline/README.md`. Run the same checks locally:

```bash
make verify            # every check; the container check needs Docker
make verify-tests      # full test suite
make verify-security   # Security Regression Suite
make verify-static     # Ruff, MyPy and Bandit (report-only)
make verify-deps       # Dependency Vulnerability Check
make verify-container  # Container Build Check
```

Rules of the Security Regression Suite:

1. No security test may be skipped. Start Redis and set `TEST_REDIS_URL=redis://localhost:6379/15` for the Redis rate limit tests.
2. The collected tests must match `tests/security/suite_manifest.json`. After you add, rename or remove a security test, run `make security-manifest` and commit the manifest with the change.
