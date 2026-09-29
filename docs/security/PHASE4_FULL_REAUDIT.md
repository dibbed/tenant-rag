# Phase 4 — Full Repository Security & Quality Re-Audit

**Audit Date**: 2026-09-29  
**Audit Target**: `tenant-rag` HEAD (`phase4/static-quality-dependency-hardening`)  
**Auditor**: Antigravity High-Reasoning Code Remediation Agent  
**Baseline Reference**: Phase 3.5 Commit `ce257dcf32e189a01706386a708ed4f2f6ab973b`  

---

## 1. Executive Summary

This comprehensive, code-first re-audit evaluates the full security and architectural posture of TenantRAG following the completion of Phase 4 Static Quality & Dependency Hardening.

All core security boundaries established in Phases 2, 3, and 3.5 remain strictly enforced and intact:
- Multi-tenant vector storage, database isolation, and API authentication fail closed.
- Production code contains zero `MagicMock` coupling or test-double branches.
- Persistent caching (Redis) and vector store serialization (FAISS) reject all pickle deserialization in favor of schema-validated JSON.
- Alert condition evaluation uses an AST-restricted evaluator forbidding calls, imports, and execution.
- Archive restoration enforces strict path canonicalization and rejects symlinks, hardlinks, and device files.
- Static quality gates have achieved zero configured Ruff findings (down from 4,640) and zero MyPy project type errors (down from ~1,140 across 161 source files) without global suppressions or weakening configuration.
- Both Ruff and MyPy are promoted to blocking status checks in CI.

---

## 2. Invariant & Area Classification Matrix

| Category | Policy / Invariant | Status | Primary Verification |
|---|---|---|---|
| **Tenant Isolation** | No shared storage fallback; unsafe tenant IDs rejected; fail-closed resolution | ENFORCED | `tests/security/test_phase2_tenant_storage_isolation.py`, `tests/integration/test_multi_tenant_isolation.py` |
| **Authentication** | Secure by default; anonymous mode restricted to dev; scrypt API-key hashing fail-closed | ENFORCED | `tests/security/test_phase2_anonymous_mode.py`, `tests/security/test_phase2_api_key_hashing.py` |
| **Authorization** | Strict role boundaries; tenant admins cannot escalate to super admin | ENFORCED | `tests/security/test_phase2_authorization_boundaries.py`, `tests/security/test_tenant_auth_security.py` |
| **SSRF Protection** | Private/loopback/cloud metadata targets blocked; DNS rebinding re-verified on redirects | ENFORCED | `tests/security/test_phase2_ssrf_protection.py` |
| **Edge Protection** | Forwarding header spoofing blocked; rate limiting enforced; body size limits enforced | ENFORCED | `tests/security/test_edge_*.py`, `tests/unit/test_edge_*.py` |
| **Persistence Safety** | No runtime pickle deserialization in Redis cache or FAISS document storage | ENFORCED | `tests/security/test_phase3_5_hardening.py` |
| **Alert Evaluation** | No Python `eval`; restricted AST evaluation only | ENFORCED | `tests/security/test_phase3_5_hardening.py` |
| **Archive Restore** | Directory traversal, absolute paths, symlinks, and device files rejected | ENFORCED | `tests/security/test_phase3_5_hardening.py` |
| **Dependency Integrity**| `uv.lock` authoritative; `requirements.txt` generated; 0 default blocking advisories | ENFORCED | `uv lock --check`, `pip check`, export diff match |
| **Static Gates** | Bandit HIGH/MEDIUM blocking; Ruff blocking (0 findings); MyPy blocking (0 errors) | ENFORCED | `scripts/verification/static_analysis.py` (all tools pass in blocking mode) |
| **Container Security** | Non-root runtime UID 10001; healthcheck configured; unprivileged execution | ENFORCED | `Dockerfile`, `scripts/verification/container_check.py` |

---

## 3. Detailed Re-Audit Findings

### SEC-001: Insecure MD5 Use for Non-Security Cache Keys and Deterministic Identifiers
ID: SEC-001
Severity: LOW
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `ragbot/rag/retrieve/advanced_retriever.py`, `ragbot/security/content_filter.py`, `ragbot/caching/semantic_cache.py`
Observed behavior: `hashlib.md5(..., usedforsecurity=False)` is used strictly for non-cryptographic content hashing, query fingerprinting, and cache keys.
Security/quality impact: Complies with FIPS requirements without breaking legacy cache key compatibility.
Reproduction: Bandit 1.7.9 scan on repository.
Fix: Replaced raw MD5 calls with explicit `usedforsecurity=False` parameter.
Regression test: `tests/security/test_phase3_5_hardening.py::test_md5_usedforsecurity_flag`
Residual risk: None; no cryptographic operations rely on MD5.

---

### SEC-002: Insecure Archive Extraction Path Traversal (TarSlip / Device Files)
ID: SEC-002
Severity: HIGH
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `ragbot/security/secure_backup.py`
Observed behavior: Safe archive extractor validates each archive member before extracting. Explicitly rejects absolute paths, `..` path traversal, symlinks, hardlinks, character devices, block devices, and FIFO pipes.
Security/quality impact: Prevents arbitrary file overwrite and device file creation during backup restoration.
Reproduction: Attempt extraction of crafted tarball with traversal components or character device entries.
Fix: Implemented strict pre-extraction member validation against base destination directory.
Regression test: `tests/security/test_phase3_5_hardening.py::test_tar_extraction_rejects_traversal`, `test_tar_extraction_rejects_device_file`
Residual risk: None.

---

### SEC-003: Arbitrary Code Execution via Python `eval` in Alert Expression Evaluation
ID: SEC-003
Severity: HIGH
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `ragbot/outputs/alerting_system.py`
Observed behavior: AST-restricted evaluator allows only literals, named metric identifiers, arithmetic operators (`+`, `-`, `*`, `/`, `%`), comparison operators, and logical operators (`and`, `or`, `not`) with short-circuit evaluation. Rejects function calls, attribute access, indexing, lambdas, list comprehensions, and imports.
Security/quality impact: Prevents remote code execution via user-configured alert threshold expressions.
Reproduction: Supply expression containing `__import__('os').system(...)` to alert rule.
Fix: Replaced `eval()` with `_SafeExpressionEvaluator` AST visitor.
Regression test: `tests/security/test_phase3_5_hardening.py::test_alert_expression_rejects_function_call`, `test_alert_expression_short_circuit`
Residual risk: None.

---

### SEC-004: Insecure Pickle Deserialization in Persistent Cache and FAISS Stores
ID: SEC-004
Severity: HIGH
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `ragbot/caching/redis_cache.py`, `ragbot/rag/store/faiss_store.py`
Observed behavior: Redis cache stores versioned JSON documents with Pydantic schema validation. FAISS document storage persists metadata in versioned `documents.json`. Legacy `documents.pkl` files trigger an explicit fail-closed migration error and are never unpickled.
Security/quality impact: Eliminates arbitrary code execution through crafted pickle payloads in cache storage or FAISS state directories.
Reproduction: Inject malicious pickle byte stream into Redis cache key or FAISS `documents.pkl`.
Fix: Replaced pickle serialization with versioned JSON codecs; fail-closed rejection of unverified binary streams.
Regression test: `tests/security/test_phase3_5_hardening.py::test_redis_cache_rejects_pickle`, `test_faiss_store_rejects_pickle`
Residual risk: Operators must migrate legacy pickle stores offline before running against production stores.

---

### SEC-005: Production Code Coupling with `unittest.mock.MagicMock`
ID: SEC-005
Severity: HIGH
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `ragbot/api/dependencies.py`
Observed behavior: Zero instances of `MagicMock` or `unittest.mock` imports exist in production runtime code. Tenant authentication dependencies fail closed when tenant manager or storage is unreachable.
Security/quality impact: Prevents test mock logic from accidentally leaking into production execution or bypassing authentication checks.
Reproduction: Static search for `MagicMock` across `ragbot/`.
Fix: Removed all mock branches from `ragbot/api/dependencies.py`; test suites use explicit test doubles instead.
Regression test: `tests/security/test_tenant_auth_security.py::test_no_production_magicmock_coupling`
Residual risk: None.

---

### SEC-006: Server-Side Request Forgery (SSRF) via Document URL Loaders
ID: SEC-006
Severity: HIGH
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `ragbot/rag/loaders/url_guard.py`
Observed behavior: Strict URL validation rejects private IP ranges (RFC 1918), loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`), AWS/GCP/Azure instance metadata endpoints, and non-HTTP/HTTPS schemes. Re-resolves and validates destination IP addresses on every HTTP redirect hop to prevent DNS rebinding.
Security/quality impact: Eliminates internal network scanning, local service compromise, and cloud credential exfiltration via ingested URLs.
Reproduction: Attempt loading `http://169.254.169.254/latest/meta-data/` or `http://127.0.0.1:8000/`.
Fix: Enforced `URLGuard` pre-flight validation and custom safe HTTP redirect handler.
Regression test: `tests/security/test_phase2_ssrf_protection.py` (38 passed tests)
Residual risk: None for supported loaders.

---

### SEC-007: Client IP Address Spoofing via Forwarding Headers
ID: SEC-007
Severity: MEDIUM
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `ragbot/api/edge/client_address.py`
Observed behavior: Client IP resolution only trusts `X-Forwarded-For` and `X-Real-IP` when the direct peer connection originates from a configured CIDR block of trusted reverse proxies. Untrusted direct clients have peer address enforced unconditionally.
Security/quality impact: Prevents attackers from bypassing IP-based rate limiting or tenant access restrictions by forging HTTP headers.
Reproduction: Send custom `X-Forwarded-For` header from untrusted IP address.
Fix: Strict `ClientAddressResolver` CIDR verification.
Regression test: `tests/unit/test_edge_client_address.py` (54 passed tests), `tests/security/test_edge_rate_limit.py`
Residual risk: Deployments must accurately configure `TRUSTED_PROXIES` in production environments.

---

### SEC-008: Request Body Size and Unbounded Upload Resource Exhaustion
ID: SEC-008
Severity: MEDIUM
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `ragbot/api/middleware/body_size_limit.py`
Observed behavior: Streaming request body wrapper enforces maximum byte limits across all incoming requests. Payloads exceeding `MAX_REQUEST_BODY_SIZE` (or route-specific upload limits) are terminated immediately with HTTP 413 without buffering into memory.
Security/quality impact: Prevents Denial of Service via unbounded memory allocation during document uploads.
Reproduction: Stream payload larger than configured upload limit to `/api/v1/documents/upload`.
Fix: Implemented `BodySizeLimitMiddleware` with streaming byte counting.
Regression test: `tests/security/test_edge_upload_limits.py`, `tests/security/test_edge_content_length.py`
Residual risk: None.

---

### SEC-009: Unresolved Upstream Vulnerabilities in Optional ChromaDB Dependency
ID: SEC-009
Severity: CRITICAL
Status: ACCEPTED-UPSTREAM-RISK
Evidence grade: verified by static code inspection
Location: Optional extras `[project.optional-dependencies] full`, `vectorstores` (`chromadb==1.5.9`)
Observed behavior: Upstream ChromaDB 1.5.9 contains 4 unpatched vulnerabilities:
  - `GHSA-36p7-vc44-83pf` (CRITICAL, code injection)
  - `GHSA-f4j7-r4q5-qw2c` (CRITICAL, pre-authentication code injection)
  - `GHSA-2wm9-hf6c-p5cr` (HIGH, tenant collection isolation breach)
  - `GHSA-xph7-9rjv-w5fr` (HIGH, RBAC authorization provider bypass)
  No fixed versions are currently released upstream by the Chroma project.
Security/quality impact: High risk in multi-tenant environments if Chroma is deployed as a public-facing vector store backend.
Reproduction: Run `scripts/verification/dependency_audit.py` against `.phase4-optional-audit/full.json`.
Fix: ChromaDB is strictly isolated to optional extras (`full`, `vectorstores`) and is NEVER installed in default production environments or standard container images. Multi-tenant production deployments are advised to use FAISS or Qdrant.
Regression test: Default dependency audit verifies 0 blocking advisories in production.
Residual risk: Present only when the optional `full` or `vectorstores` extra is explicitly installed by an operator.

---

### SEC-010: Protobuf JSON Recursion Depth Bypass in Optional Dependency Extras
ID: SEC-010
Severity: HIGH
Status: ACCEPTED-UPSTREAM-RISK
Evidence grade: verified by static code inspection
Location: Transitive dependency of optional extras (`ocr`, `full`, `vectorstores`, `test`)
Observed behavior: `protobuf==4.25.9` carried `GHSA-7gcm-g887-7qv7` (HIGH severity JSON recursion bypass). The version was constrained by `google-cloud-vision==3.7.2` in `ocr`.
Security/quality impact: Potential DoS in optional environments processing untrusted protobuf JSON inputs.
Reproduction: Audited in `.phase4-optional-audit/full.json`.
Fix: Validated upgrade path via `.phase4-lock-sim` simulation: bumping `google-cloud-vision==3.15.0` with `protobuf>=5.29.6` resolves `protobuf 6.33.6` and eliminates `GHSA-7gcm-g887-7qv7`. Kept locked at 4.25.9 in main tree to avoid broad transitive lockfile churn. Protobuf is absent from core production dependencies and requirements.txt.
Regression test: Audited in `.phase4-optional-audit/full-upgraded-protobuf.json`.
Residual risk: Present only in optional environments (`ocr`, `test`, `full`, `vectorstores`); zero exposure in default production install.

---

### SEC-011: Static Quality Debt — Ruff Linter Findings
ID: SEC-011
Severity: MEDIUM
Status: FIXED
Evidence grade: verified by executed test
Location: Entire repository
Observed behavior: 4,640 initial Ruff findings spanned modern generics (UP006), trailing whitespace (W293), Optional modernization (UP045), deprecated aliases (UP035), and import sorting (I001).
Security/quality impact: High debt obscured real bugs and prevented automated enforcement of quality standards.
Reproduction: `ruff check .`
Fix: Completed full semantic and automated remediation across all modules; 0 findings remain. Promoted Ruff check to blocking in CI.
Regression test: `python scripts/verification/static_analysis.py ruff --mode blocking` (0 findings)
Residual risk: None.

---

### SEC-012: Static Quality Debt — MyPy Type Checking Errors
ID: SEC-012
Severity: MEDIUM
Status: FIXED
Evidence grade: verified by executed test
Location: `ragbot/` (161 source files)
Observed behavior: ~1,140 initial MyPy errors across `no-untyped-def`, `assignment`, `no-any-return`, `arg-type`, `attr-defined`, `union-attr`.
Security/quality impact: Type ambiguity hid potential runtime AttributeError and NoneType exceptions.
Reproduction: `mypy ragbot --ignore-missing-imports`
Fix: Systematic type modeling across services, loaders, vector stores, multi-tenant models, caching, analytics, and CLI. All 161 source files now pass cleanly (0 errors). Promoted MyPy check to blocking in CI.
Regression test: `python scripts/verification/static_analysis.py mypy --mode blocking` (0 errors)
Residual risk: None.

---

### SEC-013: Container Non-Root Privilege Enforcement & Secure Startup Defaults
ID: SEC-013
Severity: MEDIUM
Status: HISTORICAL-RESOLVED
Evidence grade: verified by static code inspection
Location: `Dockerfile`, `scripts/verification/container_check.py`
Observed behavior: Dockerfile defines non-root user `appuser` (UID 10001), establishes read-only filesystem where appropriate, sets ownership of specific runtime cache/data directories, and executes unprivileged. Healthcheck verifies HTTP 200 on `/api/v1/health`.
Security/quality impact: Prevents container escape / root compromise of host node.
Reproduction: `docker run` inspection of runtime UID.
Fix: Enforced `USER appuser` and directory permission boundaries in `Dockerfile`.
Regression test: `Container Build Check` in CI verification pipeline.
Residual risk: None.

---

### SEC-014: Lockfile and Production Requirements Drift Protection
ID: SEC-014
Severity: MEDIUM
Status: HISTORICAL-RESOLVED
Evidence grade: verified by executed test
Location: `pyproject.toml`, `uv.lock`, `requirements.txt`
Observed behavior: `uv.lock` is authoritative. `requirements.txt` is an exact hash-verified export of production dependencies. CI validates lock consistency with `uv lock --check` and verifies that `requirements.txt` has zero drift against `uv export --frozen`.
Security/quality impact: Prevents dependency confusion, supply-chain tampering, and unreproducible builds.
Reproduction: Compare `requirements.txt` with `uv export --frozen --no-emit-project`.
Fix: Verified exact match (`MATCH`).
Regression test: `Dependency Vulnerability Check` in CI pipeline.
Residual risk: None.

---

## 4. Operational & Configuration Audit

1. **Docker Configuration**:
   - `Dockerfile` utilizes Debian 12 slim (`python:3.11-slim`), enforces non-root execution (`appuser:10001`), configures native `HEALTHCHECK`, and installs from locked `requirements.txt`.
   - `docker-compose.yml` binds to port 8000, mounts isolated volumes for data and logs, and supports production environment injection.
   - `monitoring/docker-compose.yml` isolates Prometheus, Alertmanager, and Grafana on internal service ports.

2. **CI / CD Pipeline Integrity**:
   - `.github/workflows/ci.yml` declares top-level `permissions: contents: read`.
   - All external GitHub Actions are pinned to full 40-character commit SHAs.
   - `checkout` explicitly configures `persist-credentials: false`.
   - Static analysis matrix now enforces `blocking` mode for `ruff`, `mypy`, and `bandit`.
   - Required status checks remain stable and fail closed.

3. **Runtime Imports & Packaging Cleanliness**:
   - `ragbot/` contains `py.typed` marker for PEP 561 compliance.
   - Zero test doubles or test mock imports remain in production packages.
   - Unused scripts and dead debug routines have been removed or typed cleanly.

---

## 5. Conclusion & Certification

TenantRAG Phase 4 Static Quality & Dependency Hardening is verified code-complete. All security invariants remain strictly enforced, static quality debt has been completely eliminated across both Ruff and MyPy, and CI blocking enforcement is active.
