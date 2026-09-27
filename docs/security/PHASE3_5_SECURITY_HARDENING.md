# Phase 3.5 Security Hardening

Status: implementation complete on PR #4; final documentation-only PR rerun must remain green before merge.

Scope: harden the remaining production security boundaries after the Phase 2/3 work, eliminate Bandit HIGH/MEDIUM findings, make Bandit blocking, remove executable persistence/deserialization paths, lock dependency resolution, audit optional extras, and make local verification commands preserve failure exit codes.

## Baseline

Baseline commit: `183b2fe2a19b17f82b0eb33433c9d7ce03002d24`.

Baseline Bandit 1.7.9 result:

| Severity | Before Phase 3.5 | Code-complete PR run |
|---|---:|---:|
| HIGH | 19 | 0 |
| MEDIUM | 9 | 0 |
| LOW | 182 | 177 |

The 19 HIGH findings were 18 non-security MD5 uses and one unsafe tar extraction. The MEDIUM findings included pickle deserialization, `eval`, and bind-address findings that required either remediation or a narrow, documented justification.

## Tenant authorization boundary (C7/C8)

`ragbot/api/dependencies.py` no longer imports or branches on `unittest.mock.MagicMock`.

Tenant lookup now fails closed:

- missing/invalid tenant: HTTP 403;
- inactive tenant: HTTP 403;
- unavailable tenant manager, missing trustworthy status, or unexpected backend exception: HTTP 503 with a generic client response;
- internal exception details remain in server logs and are not returned to clients.

Tests use explicit production-like fakes instead of production code recognizing test doubles.

## Safe persistence

### Redis cache

Redis cache persistence is versioned JSON only. Values are schema-validated before encoding and after decoding. Legacy pickle entries are rejected and must expire or be deleted. Runtime code never attempts to unpickle them.

### FAISS document data

The native FAISS index remains in FAISS format. Application document data moved from `documents.pkl` to versioned `documents.json`.

The JSON representation supports the data model used by current document metadata, including explicitly tagged/base64-encoded bytes and tagged tuples. Unknown tags and invalid schemas are rejected.

A legacy `documents.pkl` without a safe replacement fails with an explicit migration/rebuild error. It is never deserialized in production.

Migration policy: rebuild from trusted source documents where possible. If an operator must recover a trusted legacy pickle, do so offline in a controlled migration tool/environment, never inside the service trust boundary.

## Dynamic evaluation

Alert conditions no longer use Python `eval`. The evaluator parses an expression AST and permits only:

- numeric/boolean constants;
- named metrics and `threshold`;
- comparisons;
- boolean `and`, `or`, `not`;
- basic arithmetic `+ - * / %`;
- unary plus/minus.

Calls, attribute access, subscripting, lambdas, comprehensions, imports, and other executable constructs are rejected. Boolean operators preserve Python short-circuit behavior.

## Archive extraction

Backup restore no longer delegates paths to `tarfile.extractall`.

Before extraction, every member is validated and the restore path is resolved under the intended root. The extractor rejects:

- absolute paths;
- `..` traversal, including nested traversal;
- drive-like paths;
- symlinks and hard links;
- devices and other non-file/non-directory member types.

Files are copied only after validation.

## MD5 review

All 18 Bandit B324 findings were individually classified as non-security cache keys, deterministic identifiers/fingerprints, or deterministic test/fallback behavior. None is used for password hashing, credentials, signatures, tamper detection, or security tokens.

Those call sites retain MD5 for compatibility and explicitly pass `usedforsecurity=False`. No security-sensitive MD5 use was found in the Phase 3.5 Bandit inventory.

## Other Bandit findings

- The main API's `0.0.0.0` bind is intentional and has a narrow B104 justification.
- A `"0.0.0.0"` value in URL validation is a deny-list value, not a bind.
- The standalone health server now defaults to `127.0.0.1`; external exposure requires an explicit host.
- No broad Bandit rule skip was introduced.

Bandit blocking policy is severity-aware: HIGH/MEDIUM block; LOW remains visible.

## Dependency locking

`pyproject.toml` is the dependency source of truth. `uv.lock` is the committed transitive lock. CI pins `uv==0.12.19`.

`requirements.txt` is a generated, hash-bearing export for the production/container dependency set. CI rejects lock drift with `uv lock --check`, regenerates the production export with `uv export --frozen --no-emit-project`, and fails on a diff.

The test matrix installs `dev` + `test` from the same frozen lock. The `test` extra explicitly includes Qdrant and scikit-learn because those were part of the historical full-suite environment while remaining outside the production dependency set.

## Optional-extra security audit

Optional extras are installed from the same lock and audited in separate report-only jobs. They do not change the blocking policy for the default production environment.

Code-complete PR run 41 reported:

| Extra | Audit state | Blocking-severity findings in that optional environment |
|---|---|---|
| dev | audit pass | 0 |
| docs | audit pass | 0 |
| hf | audit pass | 0 |
| ml | audit pass | 0 |
| offline | audit pass | 0 |
| test | findings visible | protobuf HIGH |
| ocr | findings visible | protobuf HIGH |
| full | findings visible | 2 Chroma CRITICAL, 2 Chroma HIGH, protobuf HIGH |
| vectorstores | findings visible | 2 Chroma CRITICAL, 2 Chroma HIGH, protobuf HIGH |

No exception was added. Chroma stays optional because the locked Chroma release has four unresolved upstream HIGH/CRITICAL advisories without a fixed release in the audit data. The protobuf advisory has fixed versions upstream, but the current all-extras lock resolves 4.25.9 due the optional dependency graph. It remains visible for follow-up and does not affect the locked default production environment.

Default production dependency audit: 149 packages audited, 0 blocking advisories, 0 accepted exceptions, 3 MODERATE advisories.

## Verification command semantics

`make lint` no longer hides MyPy failures. `make security` no longer masks security tool failures and runs the security suite, Bandit blocking gate, and dependency gate.

`scripts/verify_pipeline.sh` mirrors policy: Ruff/MyPy are report-only, Bandit HIGH/MEDIUM is blocking, dependency verification checks lock/export drift before audit.

## Regression coverage

Phase 3.5 adds security regressions for:

- C7 fail-closed tenant lookup;
- absence of production MagicMock coupling;
- Redis JSON round trips and malicious pickle rejection;
- FAISS JSON round trips, binary metadata, and malicious legacy pickle rejection;
- allowed and malicious alert expressions, including short-circuit cases;
- safe tar extraction, traversal, absolute paths, and link rejection;
- intended MD5 compatibility behavior.

The Security Regression Suite manifest contains 345 tests.

## Verification evidence

Code-complete PR run:

- PR: #4, `Harden persistence and make Bandit blocking`
- workflow run: `36315447766`
- full suite: 1035 passed, 0 failed, 11 skipped on Python 3.10, 3.11 and 3.12;
- security suite: 345 passed, 0 failed, 0 errors, 0 skipped on Python 3.10, 3.11 and 3.12;
- Bandit: 0 HIGH, 0 MEDIUM, 177 LOW, blocking gate passed;
- locked default dependency audit: passed;
- container build/runtime check: passed as non-root;
- Ruff and MyPy remain report-only technical debt.

The latest PR workflow after documentation changes must also be green before merge. After merge, the push run on `main` must be green before Phase 3.5 is considered closed.

## Remaining risks and follow-up

1. Ruff and MyPy still contain substantial pre-existing report-only debt. They were not weakened or hidden in this phase.
2. Chroma remains optional and carries unresolved upstream advisories. Do not treat the `vectorstores` or `full` extra as equivalent to the hardened default production installation.
3. Optional environments currently resolve vulnerable protobuf 4.25.9. Upgrade the constraining optional dependency graph and regenerate the lock in a later dependency-maintenance change.
4. Legacy trusted FAISS pickle data requires an offline migration/rebuild. The production runtime intentionally refuses to load it.
5. Data at rest is not encrypted by TenantRAG; deployments remain responsible for volume/disk encryption.
