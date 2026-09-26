# Security Verification Pipeline

The Verification Pipeline checks every change to `main` for security regressions. It runs on every pull request to `main` and on every push to `main`, on Python 3.10, 3.11 and 3.12. It makes the security controls of Phases 2 and 3 (authentication, authorization, tenant isolation, SSRF protection, edge protection) testable in CI, so that a change cannot remove or weaken them without a failed, visible check.

Requirements: REQ-MTS-CI-001 to REQ-MTS-CI-005 (Multi-Tenant Security, Security Verification Pipeline).

## Checks

The workflow is `.github/workflows/ci.yml` (workflow name "Verification Pipeline").

| Check (status check name) | Mode | What it verifies | It fails when |
|---|---|---|---|
| `Tests (Python 3.10)`, `Tests (Python 3.11)`, `Tests (Python 3.12)` | Blocking | The full test suite, with Redis | A test fails or has an error, a test file cannot be collected, or no test runs. Skipped tests are allowed; the report lists each one with its reason. |
| `Security Regression Suite (Python 3.10)`, `(Python 3.11)`, `(Python 3.12)` | Blocking | The security tests of `tests/security/suite_manifest.json`, in their own job, with Redis | A security test fails, has an error, is skipped or is marked xfail. A security test file is skipped or cannot be collected. A test of the manifest is missing, or a collected test is not in the manifest. |
| `Static Analysis (ruff, report-only)` | Report-only | The Ruff rules of `pyproject.toml` (Ruff 0.12.12, `ruff check .`) | Ruff reports findings. The run is not blocked. |
| `Static Analysis (mypy, report-only)` | Report-only | Types in `ragbot` (MyPy 1.10.1, `mypy ragbot --ignore-missing-imports`, as `make type-check`) | MyPy reports errors. The run is not blocked. |
| `Static Analysis (bandit, report-only)` | Report-only | Insecure code patterns in `ragbot` (Bandit 1.7.9 with the `[tool.bandit]` settings) | Bandit reports findings. The run is not blocked. |
| `Dependency Vulnerability Check` | Blocking | Known advisories for every installed package (pip-audit 2.10.1 with the OSV database) | An advisory is HIGH, CRITICAL or of unknown severity and has no accepted exception. An exception entry is not valid. A package cannot be audited. |
| `Container Build Check` | Blocking | The Docker image, started with its default settings | The build fails. The container stops or does not answer `GET /health` with HTTP 200 within 300 seconds. A health endpoint or the image HEALTHCHECK is not healthy. A request without credentials is not refused with HTTP 401. A process runs as UID 0. |
| `Verification Summary` | Blocking | The results of all checks above | A Blocking Check failed, had an error or has no report. |

The workflow runs on `ubuntu-24.04` with read-only repository permissions. Every action is pinned to a commit SHA, and checkout does not keep the token. Runs of the same pull request cancel older runs. Pushes to `main` are never cancelled.

A Report-Only Check keeps the exit status of its tool: findings mark the check as failed, and `continue-on-error` keeps the workflow result green. So the findings are visible in every run and in the Verification Summary, but they do not block a merge.

## Required status checks

Branch protection of `main` requires these checks, from GitHub Actions:

- `Tests (Python 3.10)`, `Tests (Python 3.11)`, `Tests (Python 3.12)`
- `Security Regression Suite (Python 3.10)`, `Security Regression Suite (Python 3.11)`, `Security Regression Suite (Python 3.12)`
- `Dependency Vulnerability Check`
- `Container Build Check`
- `Verification Summary`

The branch must be up to date with `main` before a merge. The rules apply to administrators too. Force pushes and branch deletion are not allowed. The static analysis checks are not required.

If you rename a job or change the Python versions, update the required checks in the branch protection settings in the same change. Otherwise a pull request waits for a check that never reports.

## Security Regression Suite

The suite is the set of tests that verify the security controls:

- `tests/security`: authentication and API keys, authorization boundaries, tenant storage isolation, fail-closed storage, SSRF protection, rate limiting, CORS and request size limits
- `tests/unit/test_edge_client_address.py`, `tests/unit/test_edge_cors_policy.py`, `tests/unit/test_edge_rate_limit_store.py`
- `tests/integration/test_edge_rate_limit_redis.py` (real Redis) and `tests/integration/test_edge_uvicorn_server.py`
- `tests/integration/test_multi_tenant_isolation.py`

`tests/security/suite_manifest.json` lists these paths and the node id of each of the 322 tests. The suite runs in its own job and collects only these paths. It does not depend on the full test suite, and a failure in another test file cannot hide it. CI provides Redis, so the Redis tests run.

Rules:

1. **No skipped security test.** A skipped or xfail test fails the check. The job log, an annotation and the Verification Summary name the test and the skip reason.
2. **Failed tests are named.** Each failed test is listed with its error message.
3. **The collected tests must match the manifest.** A test that the manifest lists but the run does not collect (removed or renamed) fails the check as missing. A collected test that the manifest does not list fails the check as not listed.
4. **Removals are visible.** The check compares the manifest with the manifest of the base commit. The Verification Summary lists every security test that the change removes or adds, and a warning annotation lists the removed tests.

To add, rename or remove a security test:

1. Change the test.
2. Run `make security-manifest` (or `python scripts/verification/run_suite.py security --update-manifest`).
3. Commit `tests/security/suite_manifest.json` with the test change.

The manifest diff then shows the change in review. A pull request that removes a security test must explain why.

## Static analysis (Report-Only)

Ruff, MyPy and Bandit use the versions pinned in the `dev` extra of `pyproject.toml` and the settings in `pyproject.toml`. Each run shows the number of findings, the most frequent codes and, for Bandit, file annotations for the HIGH findings.

To promote a check to a Blocking Check:

1. Fix the findings, or suppress each one with a justification.
2. Set `mode: blocking` for the tool in the `static-analysis` matrix of `.github/workflows/ci.yml`.
3. Add `Static Analysis (<tool>, blocking)` to the required status checks of `main`.

## Dependency Vulnerability Check

- **Tool:** pip-audit 2.10.1 (`scripts/verification/requirements-audit.txt`) in its own virtual environment, so its own dependencies are not audited. Advisories come from the OSV database.
- **Scope:** every package that `pip install -r requirements.txt` and `pip install -e ".[dev]"` install on Python 3.11, the Python version of the container image. The project itself is installed in editable mode and is not audited. A package that pip-audit cannot audit fails the check.
- **Severity:** the severity of the GitHub-reviewed advisory (GHSA) in OSV; without one, the CVSS v3 base score in OSV. Findings of one advisory under several ids (for example PYSEC and GHSA) count once.
- **Blocking:** HIGH, CRITICAL and unknown severity. An unknown severity blocks, so an advisory cannot pass because its record is incomplete. If the OSV lookup fails, the check reports an error.
- **Non-blocking:** MODERATE and LOW advisories. The Verification Summary lists them.
- **Optional extras** (`vectorstores`, `full`, `ocr`, `offline`, `ml`, `hf`, `docs`) are not installed and not audited.

### Accepted exceptions

An advisory that cannot be remediated can be accepted in `.github/dependency-audit-exceptions.json`. Use an exception only when the package cannot be upgraded, removed or moved out of the default installation.

```json
{
  "exceptions": [
    {
      "id": "GHSA-xxxx-xxxx-xxxx",
      "package": "example-package",
      "version": "1.2.3",
      "justification": "Why the vulnerable code cannot be reached in TenantRAG.",
      "mitigation": "What limits the risk until a fixed version is available.",
      "owner": "@github-handle",
      "review_by": "2027-01-31"
    }
  ]
}
```

- `id` is the advisory id or one of its aliases. `version` is the installed version. After an upgrade the entry no longer applies and is reported as unused.
- `review_by` must not have passed and must be at most 366 days ahead. After that date the entry is invalid, and the check fails until the entry is reviewed.
- Placeholder values (`TBD`, `TODO`, `unknown`, `n/a` and similar) and wildcards are rejected. Each field is required.
- The Verification Summary lists every accepted exception with its owner and review date.
- `python scripts/verification/dependency_audit.py validate-exceptions` checks the file.

There are no accepted exceptions.

### Remediation in this change

Before this change, the audit found HIGH or CRITICAL advisories in 17 installed packages. They were remediated without exceptions:

| Package | Before | After | Reason |
|---|---|---|---|
| langchain, langchain-openai, langchain-community | 0.2.6, 0.1.8, 0.2.6 | removed | No code imports them. They also brought langchain-core, langchain-text-splitters and langsmith, which had CRITICAL and HIGH advisories. The latest 0.3 releases still have a HIGH advisory in langchain-core that is fixed only in 1.x. |
| nltk | 3.8.1 | removed | No code imports it. The latest release (3.10.3) still has a HIGH advisory without a fix (GHSA-8mgp-746c-j5xp). |
| chromadb | >=0.5.0 (1.5.9) | optional `vectorstores` extra | 1.5.9 is the latest release. It has 2 CRITICAL and 2 HIGH advisories without a fix, in the Chroma server HTTP API: GHSA-f4j7-r4q5-qw2c, GHSA-36p7-vc44-83pf, GHSA-2wm9-hf6c-p5cr, GHSA-xph7-9rjv-w5fr. TenantRAG uses only the embedded client. |
| fastapi, starlette, python-multipart | 0.111.0, 0.37.2, transitive | 0.141.1, 1.7.0, 0.32 pinned | Starlette advisories GHSA-f96h-pmfr-66vw, GHSA-wqp7-x3pw-xc5r, GHSA-82w8-qh3p-5jfq. FastAPI 0.141 does not install python-multipart, which the upload routes need. |
| aiohttp | 3.9.5 | 3.14.3 | GHSA-6mq8-rvhq-8wgg, GHSA-cq5v-8q36-5273 |
| cryptography | 42.0.8 | 50.0.1 | GHSA-537c-gmf6-5ccf, GHSA-r6ph-v2qm-q3c2, GHSA-jwv3-5hgf-82ww |
| pyjwt | 2.8.0 | 2.15.0 | GHSA-752w-5fwx-jx9f, GHSA-xgmm-8j9v-c9wx, PYSEC-2025-183 |
| orjson | 3.10.5 | 3.12.0 | GHSA-hx9q-6w63-j58v |
| Pillow | 10.4.0 | 12.3.0 | 13 HIGH advisories |
| pypdf | 4.2.0 | 6.19.0 | GHSA-5xf7-4p34-54qr, GHSA-g867-7843-wf8q |
| torch | 2.8.0 | 2.14.0 | PYSEC-2025-203, PYSEC-2025-204, PYSEC-2026-139, GHSA-63cw-57p8-fm3p |
| transformers, sentence-transformers, huggingface_hub, tokenizers | 4.56.2, 5.1.1, <1.0, <=0.23.0 | 5.17.0, 6.1.0, >=1.5,<2.0, >=0.23.1,<0.24 | 8 HIGH advisories in transformers 4.x, 5 of them without a fix in 4.x. The other packages follow the transformers 5 requirements. |
| mkdocs-material | 9.5.27 | 9.7.7 | Allows pymdown-extensions with the fix for GHSA-gm37-52c6-37mw |
| requests, accelerate | 2.32.3, 1.10.1 | 2.34.2, 1.15.0 | MODERATE advisories |

Test changes that the remediation needed:

- aioresponses 0.7.9, the latest release, builds aiohttp responses without the `stream_writer` argument that aiohttp 3.14 requires (aio-libs/aiohttp#12815). `tests/conftest.py` gives this argument a default for the responses that aioresponses creates. Application code is not changed.
- Seven tests create a `chroma` store through `VectorStoreFactory` with a mocked Chroma class. The factory uses the class only when chromadb can be imported, so these tests now skip when chromadb is not installed. Install the `vectorstores` extra to run them.

## Container Build Check

`scripts/verification/container_check.py --build` does these steps:

1. **build:** `docker build` of the repository `Dockerfile`.
2. **start:** `docker run` with no environment variables, so the image defaults apply: production mode, no credentials, no LLM key. The port is published only on `127.0.0.1:18000`.
3. **ready:** poll `GET /health` until HTTP 200, for at most 300 seconds. The check stops at once when the container exits.
4. **health:** `GET /health` and `GET /api/v1/health` answer HTTP 200 with a `status` field, and the image HEALTHCHECK reports `healthy` within 180 seconds. An image without a HEALTHCHECK fails.
5. **auth:** `POST /api/v1/query` and `POST /api/v1/documents/reset` without credentials must answer HTTP 401.
6. **user:** the effective UID of process 1 and of every other process in the container must not be 0. The image runs as `appuser` (UID 10001).

The container is removed at the end, also after a failure. A second workflow step with `if: always()` removes every container with the label `tenant-rag-verification`. A failed check shows the failed step, the reason and the last 150 lines of the container log.

## Verification Summary

The `Verification Summary` job runs after all other checks, also when one of them fails. It writes a table (Check, Mode, Result, Findings/Details) to the job summary of the workflow run. Sections follow for failed Blocking Checks, the Security Regression Suite (manifest changes, failed and skipped tests), the Dependency Vulnerability Check (blocking advisories, accepted exceptions, non-blocking advisories), the Container Build Check (step results, runtime user, container log on failure) and the static analysis. A notice annotation gives the overall result.

Each check also uploads its JSON report as an artifact named `verification-*`. GitHub keeps the artifacts for 14 days.

## Run the checks locally

```bash
make verify             # every check; the container check needs Docker
make verify-tests       # full test suite
make verify-security    # Security Regression Suite
make verify-static      # Ruff, MyPy and Bandit (report-only)
make verify-deps        # Dependency Vulnerability Check
make verify-container   # Container Build Check
make security-manifest  # update the manifest after a security test change
```

The targets call `bash scripts/verify_pipeline.sh CHECK ...`, which uses the same tools and policies as CI. The Redis tests of the Security Regression Suite need a Redis server and `TEST_REDIS_URL=redis://localhost:6379/15`; without them these tests are skipped, and the suite fails. The reports and the summary go to `$TMPDIR/tenant-rag-verification-<timestamp>` (set `VERIFY_OUT_DIR` to change it). Set `PYTHON` to choose the interpreter.

## Troubleshooting

| Result | What to do |
|---|---|
| Security Regression Suite: security test(s) skipped | Find the skip reason in the job log or the Verification Summary. Provide the missing service or setting. Do not add `skip` or `xfail` to a security test. |
| Security Regression Suite: tests not in the manifest | Run `make security-manifest` and commit the manifest. |
| Security Regression Suite: tests missing | A security test was removed or renamed. Restore it, or update the manifest and explain the removal in the pull request. |
| Dependency Vulnerability Check: blocking advisory | Upgrade the package to a fixed version. If there is no fix, remove the package or move it out of the default installation. An accepted exception is the last option. |
| Dependency Vulnerability Check: error, OSV lookup failed | A network problem. Run the job again. |
| Container Build Check: ready or health failed | Read the container log in the job log or the Verification Summary. |
| Verification Summary: no report | The job of that check did not write a report. Open that job. |

## Files

- `.github/workflows/ci.yml`: the workflow
- `scripts/verification/run_suite.py` and `scripts/verification/pytest_plugin/verification_outcomes.py`: test suite runner, Security Regression Suite gate and manifest handling
- `scripts/verification/static_analysis.py`: Ruff, MyPy and Bandit checks
- `scripts/verification/dependency_audit.py` and `scripts/verification/requirements-audit.txt`: Dependency Vulnerability Check
- `scripts/verification/container_check.py`: Container Build Check
- `scripts/verification/summary.py`: Verification Summary
- `scripts/verify_pipeline.sh` and the `verify*` targets of the `Makefile`: local runs
- `tests/security/suite_manifest.json`: security test list
- `.github/dependency-audit-exceptions.json`: accepted exceptions
- `tests/verification/`: tests of the pipeline tools
