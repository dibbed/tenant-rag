# Phase 3 Edge Protection: Verification and Security Review

| Item | Value |
|---|---|
| Date | 2026-09-26 |
| Reviewed change | Edge Protection, commit `7cbe6e5` ("Implement edge protection hardening") |
| Scope | Rate limiting, CORS and upload protection (audit findings C9, C10, C11), and a regression check of tenant isolation, authentication, authorization, API keys and SSRF (Phase 2) |
| Result | The edge protections work as documented. One defect was found and fixed in this review (F1). No regression was found in the Phase 2 protections. Open risks are listed below. |

## How this review was done

1. Code review of `ragbot/api/edge/`, `ragbot/api/middleware/`, `ragbot/api/app.py`, `ragbot/api/dependencies.py`, `ragbot/api/routes/` and `ragbot/main.py`.
2. The full test suite in GitHub Actions on Python 3.10, 3.11 and 3.12, with a Redis 7 service for the shared rate limit store tests (workflow run 36239836490).
3. End-to-end checks against the real entrypoint: `python main.py` with production defaults (`ENVIRONMENT=production`, no trusted proxy, no CORS origin), driven over TCP.
4. Dependency audit (`pip-audit`) and static analysis (`bandit`, `ruff`, `mypy`), report only.

### Test results

| Python | Tests | Passed | Failed | Skipped | Duration |
|---|---|---|---|---|---|
| 3.10 | 936 | 935 | 0 | 1 | 148.5 s |
| 3.11 | 936 | 935 | 0 | 1 | 136.6 s |
| 3.12 | 936 | 935 | 0 | 1 | 152.0 s |

| Group | Tests | Result on every Python version |
|---|---|---|
| Phase 2 security (`tests/security/test_phase2_*.py`, `tests/security/test_tenant_auth_security.py`) | 139 | All passed |
| Edge Protection (`test_edge_*.py` in `tests/security`, `tests/unit` and `tests/integration`) | 180 | All passed |
| All other tests | 617 | 616 passed, 1 skipped |

The skipped test (`test_qa_chain_quality_metrics_integration`) needs a real OpenAI API key. It is not a security test. No security test was skipped: the Redis integration tests ran against the CI Redis service.

### End-to-end checks of `python main.py`

| Check | Result |
|---|---|
| Start with `SECURITY_CORS_ALLOWED_ORIGINS=*` in production | Refused: exit code 1, the error names the setting |
| Start with `SECURITY_TRUSTED_PROXIES=*` | Refused: exit code 1, the error names the setting |
| Startup log | States: no trusted proxy, per-instance counting, no browser origin allowed, the 413 limit |
| 11 requests, each with new forged `X-Forwarded-For`, `X-Real-IP`, `Forwarded`, `CF-Connecting-IP` and `True-Client-IP` values | 10 x `401`, then `429` |
| Behind a trusted proxy (`SECURITY_TRUSTED_PROXIES=127.0.0.1`), 12 different reported clients | 12 x `401`, no `429` |
| Behind a trusted proxy, a new forged left-hand `X-Forwarded-For` entry and a new `X-Real-IP` in each request | 10 x `401`, then `429` |
| 10 health checks after the address reached its limit | 10 x `200`, never `429` |
| Preflight from `https://evil.example` with default settings | `400`, no `Access-Control-Allow-Origin` |
| Simple request with a cookie from an unknown origin | No `Access-Control-Allow-Origin` |
| Upload with `Content-Length` of 60 MiB and `Expect: 100-continue` | `413` at once; the server did not ask for the body |
| 80 MiB upload streamed without a declared size | `413` after 53 MiB were sent; no increase in peak memory |
| 40 MiB file part inside the limit | Parsed to disk: 1.1 s, no increase in peak memory |
| 40 MiB form field without a file name inside the limit | Parsed in memory: 2.2 s, peak memory +79 MiB (see R2) |

## Verified protections

### Rate limiting (C9)

- **Client identity.** The client address is the TCP peer. Forged forwarding headers do not create new counters (tests in `tests/security/test_edge_rate_limit.py` and the end-to-end checks).
- **Trusted proxies.** `X-Forwarded-For` is read only when the TCP peer is listed in `SECURITY_TRUSTED_PROXIES`, from right to left. Forged left-hand entries and `X-Real-IP` have no effect. Catch-all and invalid entries stop startup (tests and end-to-end checks).
- **Forwarded headers in uvicorn.** `python main.py` passes `proxy_headers=False` to uvicorn (`tests/unit/test_entrypoints.py`). The end-to-end checks ran through this entrypoint.
- **Subjects.** Authenticated requests count per principal; failed credentials count per client address; health checks and documentation are never counted; each request counts once (tests).
- **Distributed and local behavior.** Without `SECURITY_RATE_LIMIT_STORAGE_URL`, each instance counts on its own and the startup log says so. With Redis, two application instances share one counter, the limit is exact under 50 concurrent requests, and records expire with the window (integration tests with Redis 7). A Redis outage falls back to per-instance counting and logs one warning (tests).
- **Secure defaults.** No trusted proxy, per-instance counting, 10 requests per 60 seconds.
- **Documentation.** `docs/features/edge-protection/README.md`, `SECURITY.md` section 6, `docs/configuration.md`, `docs/DEPLOYMENT.md` and `env.example` describe the settings and the deployment requirements.

### CORS (C10)

- **Default.** No origin is allowed (tests and end-to-end checks).
- **Production.** `*` stops startup when `ENVIRONMENT` is not `development` (tests and end-to-end checks).
- **Development.** `*` is accepted only without credentials, and no local origin is allowed implicitly (tests).
- **Allowed origins.** Listed origins are matched exactly after normalization. Lookalike origins (other scheme, port, subdomain or suffix) are refused (tests).
- **Invalid origins.** `null`, paths, queries, user information and wildcards inside an origin stop startup (tests).
- **No accidental wildcard.** With the default configuration no response carries `Access-Control-Allow-Origin`, also with cookies (tests and end-to-end checks).

### Upload protection (C11)

- **Where the size is checked.** `BodySizeLimitMiddleware` checks every request body before the route runs: a declared `Content-Length` before any byte is read, a streamed body while it is read. The upload route then copies the file to disk in 1 MiB chunks and applies the exact limit (a file of exactly the limit is accepted, one byte more is refused).
- **Memory safety.** A 32 MiB upload peaks below 8 MiB of Python memory, and refusing a 40 MiB streamed upload peaks below 6 MiB (tests). End to end, a refused 80 MiB stream caused no measurable increase in peak memory.
- **Streaming behavior.** Reading stops when the limit is passed; the client gets `413` with `Connection: close`. With `Expect: 100-continue`, the body is never requested.
- **Error handling.** `413` states the limit; an invalid `Content-Length` gets `400`; refused uploads start no ingestion and leave no temporary files (tests).

### Phase 2 protections (regression check)

- Tenant storage isolation, API key hashing, authorization boundaries, anonymous-mode defaults and SSRF protection: the 139 Phase 2 security tests pass unchanged on every Python version.
- The Edge Protection change adds rate limit counting before the `401` answers in `get_current_principal`. It changes no authentication or authorization decision and adds no route.

## Finding fixed in this review

**F1: a malformed `Content-Length` caused `HTTP 500` (Low).** `str.isdigit()` accepts Unicode digits such as `²` that `int()` refuses, and `int()` refuses strings with more than 4300 digits. `BodySizeLimitMiddleware` then raised `ValueError`. Uvicorn rejects such headers before the application sees them, but other ASGI servers may pass them on.

- Fix: only ASCII digits are accepted, otherwise `400`. A value with more than 18 digits gets `413` without conversion.
- Regression test: `tests/security/test_edge_content_length.py`. Its 4 cases fail on the previous code and pass with the fix.

## Remaining risks

| ID | Severity | Risk |
|---|---|---|
| R1 | High | **Dependencies with published advisories.** `pip-audit` reports 367 advisory entries in 26 of 253 installed packages. Relevant to the API edge: `starlette 0.37.2` (CVE-2024-47874, fixed in 0.40.0; CVE-2025-54121, fixed in 0.47.2; later advisories fixed in 1.x), `aiohttp 3.9.5` (used for URL ingestion), `pypdf 4.2.0` and `pillow 10.4.0` (parse uploaded files), `pyjwt 2.8.0`, `cryptography 42.0.8`, `requests 2.32.3` and the `langchain` packages. FastAPI 0.111.0 pins Starlette below 0.38, so a Starlette upgrade needs a FastAPI upgrade. |
| R2 | Medium | **Multipart form fields without a file name are kept in memory** (CVE-2024-47874). The request size limit caps one field at about 50 MB, but not its cost: a 40 MiB field took 2.2 s and raised peak memory by 79 MiB. Parallel requests multiply this. Fixed by the Starlette upgrade in R1. |
| R3 | Medium | **Health checks can be expensive.** `/health` and `/api/v1/health` need no credentials and are never rate limited (required by REQ-MTS-EDGE-002). `IntegrationService.health_check()` calls `QAChain.health_check()`, which runs `answer("What is the capital of France?")`: a retrieval and an LLM call. In the end-to-end run the health checks answered at once and made no LLM call, so this path did not run in that setup. It must be checked with a configured LLM. The health response also returns exception text (C13). |
| R4 | Medium | **URL ingestion has no download limit.** `URLLoader` and `fetch_text_safely()` read the whole response with `response.text()`. `max_content_length` (10 MB) is defined but not used. Only the 20-second timeout limits the size. Callers with ingest permission can make the service hold very large responses in memory. |
| R5 | Medium | **Requests with a credential header are counted after the body.** Such a request skips the pre-body count, so its body (up to the upload limit) is parsed, and for a fake key scrypt runs, before it is counted. One address can keep many large requests in flight before `429` applies. |
| R6 | Medium | **Per-instance counting.** Without `SECURITY_RATE_LIMIT_STORAGE_URL`, `WORKERS` greater than 1 multiplies the effective limit. The same happens during a Redis outage. |
| R7 | Low | **Limits per address only.** A client with many addresses (IPv4 pools, IPv6 /48 or wider) gets one counter per address or /64. There is no global or per-tenant limit. |
| R8 | Low | **Large JSON bodies.** The query and text routes accept bodies up to the upload limit (50 MB). `QueryRequest.question` has no maximum length. |
| R9 | Low | **Unix domain sockets.** A connection without a TCP peer has no client address, so all such clients share one counter and trusted proxies cannot match. |
| R10 | Low | **Static analysis outside the edge code.** `bandit` reports 211 findings in `ragbot/`: 19 high (18 MD5 uses for cache keys; `tarfile.extractall` without member checks in `ragbot/security/secure_backup.py`) and 9 medium (pickle loading in the FAISS store and the Redis cache; `eval` in `ragbot/monitoring/alert_manager.py`; binding to all interfaces). No finding is in the edge modules. `mypy` finds no issue in the 9 edge modules; `ruff` reports 2 style notes (type alias syntax). |
| R11 | Low | **CI does not block unsafe changes.** See "CI verification" below. |

## Recommended next actions

1. **Upgrade the web stack and the file parsers** (R1, R2): FastAPI and Starlette to versions without known advisories (Starlette 0.47.2 or later), then `aiohttp`, `pypdf`, `pillow`, `pyjwt`, `cryptography` and `requests`. Run the full suite on every supported Python version.
2. **Make health checks cheap** (R3): a liveness check without model or LLM calls, and a deep check that is cached or needs credentials. Remove exception text from the response.
3. **Limit URL downloads** (R4): stream the response and stop at `max_content_length`; refuse larger `Content-Length` values before reading.
4. **Security Verification Pipeline** (R11): required status checks, a blocking security suite that fails on skipped tests, report-only `ruff`, `mypy` and `bandit`, a dependency audit that blocks high and critical advisories, and a container build check.
5. **Smaller JSON limits** (R8): a body limit for the query route and a maximum question length.
6. **Early refusal for blocked addresses** (R5, optional): refuse requests with a credential before the body is read when their address is already over its failed-credential limit.
7. **Deployment settings** (R6, R9): set `SECURITY_RATE_LIMIT_STORAGE_URL` wherever more than one worker or instance runs; connect the proxy to the service over TCP.
8. **Triage the bandit findings** (R10), starting with `tarfile.extractall`, `eval` and pickle loading.

## CI verification

Current pipeline: `.github/workflows/ci.yml` runs `pytest -v` on push and pull request to `main`, on Python 3.10, 3.11 and 3.12, with a Redis service. Security tests run as part of the full suite, and a failing test fails the job.

Missing items for the Security Verification Pipeline feature (REQ-MTS-CI-001 to REQ-MTS-CI-005):

| Requirement | Missing |
|---|---|
| REQ-MTS-CI-001 | `main` is not protected and has no required status checks, so a failing run blocks neither a merge nor a direct push. No verification summary lists each check. |
| REQ-MTS-CI-002 | The security suite is not a separate blocking check. A skipped security test does not fail the run. A removed security test is not reported. |
| REQ-MTS-CI-003 | No style, type or insecure-pattern check runs in CI. |
| REQ-MTS-CI-004 | No dependency vulnerability check runs in CI (see R1 for the current result). |
| REQ-MTS-CI-005 | No container build check (build, start with defaults, health check, unauthenticated request refused, non-root user). |
| General | The workflow does not restrict token permissions, pins actions by tag instead of commit, and sets no job timeout. |

## Documentation corrected in this review

- `README.md` and `README.fa.md`: API key format and storage (salted scrypt, `rgb_<key_id>_<secret>`), behavior when multi-tenancy is disabled (`401` unless explicit development mode), request path diagram (trusted proxy, CORS, rate limit, size limit), test counts.
- `docs/ARCHITECTURE.md` and `docs/ARCHITECTURE.fa.md`: request path diagram and edge protection description; in the Persian file also the key format, key storage and single-tenant behavior.
- `docs/API.md` and `docs/FAQ.md`: key format and storage, single-tenant behavior, reset permissions, rate limit defaults, text limit in UTF-8 bytes.
- `SECURITY.md`: measured cost of CVE-2024-47874 and a link to this review.
- `env.example` was reviewed and needed no change.

Not changed: `CHANGELOG.md` and `docs/BASELINE_AUDIT.md` are historical records. `docs/SOCIAL_PREVIEW.md` still says "SHA-256 Auth" in its design text, and the changelog has no Phase 2 or Phase 3 entry.

## Repository cleanup

- Temporary branches of Phase 2 (`phase2/security-output`, `phase2/security-workspace`) and of this review are deleted. `main` has only `.github/workflows/ci.yml` and no workspace scripts or generated artifacts.
- Kept: `scripts/verify_baseline.sh` (Phase 1 verification script, used by `docs/BASELINE_AUDIT.md`) and the project documents `ragbot_project_guide.docx`, `ragbot_technical_guide.docx` and `ragbot_project_questions.txt`.
- For the owner to decide: `scripts/final_validation.sh` is an empty file from the initial commit and nothing refers to it.
