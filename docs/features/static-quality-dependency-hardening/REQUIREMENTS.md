# Phase 4 — Static Quality & Dependency Hardening — Requirements

## Status and Baseline

- Baseline commit: `ce257dcf32e189a01706386a708ed4f2f6ab973b`
- Feature branch: `phase4/static-quality-dependency-hardening`
- Local interpreter: `F:\tenant-rag\venv\Scripts\python.exe` (Python 3.12.8)
- Existing user-owned workspace change: deleted `.cursorignore`, intentionally unstaged and out of scope.
- Remote `main` matched the baseline at preflight; latest verified main workflow was Run #53.
- Fresh Ruff baseline: **4640 findings**.
- Fresh MyPy baseline is intentionally deferred until Ruff is green, per the required phase order.
- Optional dependency baselines will be reproduced after Ruff and MyPy cleanup.

### Ruff baseline inventory

| Rule | Count | Main action |
|---|---:|---|
| UP006 | 1776 | Safe modernization to built-in generics |
| W293 | 684 | Safe whitespace cleanup |
| UP045 | 595 | Modernize Optional syntax where safe |
| UP035 | 258 | Remove deprecated typing aliases/imports |
| RUF010 | 150 | Safe explicit f-string conversions |
| RUF002 | 134 | Review ambiguous Unicode in docstrings |
| RUF003 | 122 | Review ambiguous Unicode in comments |
| RUF001 | 106 | Review ambiguous Unicode in strings |
| I001 | 97 | Import ordering |
| SIM105 | 84 | Review simplification semantics |
| F401 | 74 | Remove genuinely unused imports |
| PERF203 | 59 | Manual loop/exception performance review |
| Q000 | 57 | Quote normalization |
| PERF401 | 37 | Manual list-building simplification |
| SIM102 | 29 | Manual nested-if simplification |
| UP038 | 29 | Modernize isinstance unions |
| F841 | 25 | Review unused locals |
| ARG001 | 25 | Review intentionally unused arguments |
| RUF013 | 23 | Explicit optional annotations |
| F541 | 21 | Remove redundant f prefixes |
| B905 | 20 | Add explicit zip strictness |
| Other configured rules | 201 | Manual/safe batch review |
| **Total** | **4640** | |

Scope distribution:

| Scope | Findings |
|---|---:|
| `ragbot/` | 3981 |
| `tests/` | 420 |
| `examples/` | 161 |
| `benchmarks/` | 44 |
| `scripts/` | 27 |
| repository-root / monitoring files | 7 |

Top files at baseline include `ragbot/rag/store/faiss_store.py` (158), `ragbot/services/rag_service.py` (135), `ragbot/outputs/log_aggregator.py` (109), and `ragbot/caching/redis_cache.py` (107).

## REQ-SQDH-RUFF-001 — Re-baseline Ruff

Acceptance criteria:

- Run the configured Ruff scope against current HEAD.
- Record exact findings and rule counts.
- Record main scope and high-density files.
- Historical counts are not treated as current facts.

## REQ-SQDH-RUFF-002 — Resolve Ruff debt safely

Acceptance criteria:

- Reduce configured Ruff findings to zero without changing intentional behavior.
- Apply only reviewed safe fixes automatically.
- Handle semantic/unsafe findings manually.
- Do not hide debt using global ignores, repository-wide noqa, or large exclusions.
- Any narrow exception must be justified locally.

## REQ-SQDH-RUFF-003 — Make Ruff blocking

Acceptance criteria:

- Ruff passes with zero configured findings.
- CI changes Ruff from report-only to blocking only after local green evidence.
- Verification Summary treats Ruff as blocking.
- Workflow/summary tests prove the policy.
- Required-check configuration is updated only after the stable check name is verified.

## REQ-SQDH-MYPY-001 — Re-baseline MyPy

Acceptance criteria:

- Run the current MyPy target only after Ruff is green and stable.
- Record exact error count, affected files, error codes, and module families.
- Distinguish first-party typing debt from third-party missing stubs.

## REQ-SQDH-MYPY-002 — Eliminate project type errors

Acceptance criteria:

- Resolve real first-party type errors while preserving behavior.
- Prefer explicit type modeling, Optional handling, typed aliases, Protocols, TypedDicts, dataclasses, and generics.
- Do not use global `ignore_errors`, blanket strictness weakening, production exclusions, or mass `type: ignore`.
- Third-party overrides must remain narrow and documented.
- Do not replace useful types with `Any` merely to satisfy MyPy.

## REQ-SQDH-MYPY-003 — Make MyPy blocking

Acceptance criteria:

- Configured project MyPy target has zero project errors.
- CI changes MyPy to blocking after green evidence.
- Verification Summary and workflow tests reflect the new policy.
- Required checks are updated safely only after check-name verification.

## REQ-SQDH-DEPS-001 — Audit every optional dependency environment

Acceptance criteria:

- Re-read and audit every currently declared extra independently from the frozen lock.
- Record package count and available severity counts per extra.
- Trace vulnerable transitives to their parent dependencies.
- Keep optional-risk posture separate from default production posture.

Current declared extras at preflight are `dev`, `full`, `offline`, `ocr`, `ml`, `hf`, `vectorstores`, `docs`, and `test`; this list must be re-read before dependency changes are finalized.

## REQ-SQDH-DEPS-002 — Investigate protobuf upgrade path

Acceptance criteria:

- Reproduce which extras resolve the vulnerable protobuf path.
- Identify constraining parent dependencies.
- Determine whether a compatible fixed version exists.
- If compatible, update constraints/lock and test affected extras.
- If no compatible fix exists, document exact blocker and exposure without fabricated exceptions.

## REQ-SQDH-DEPS-003 — Handle Chroma risk explicitly

Acceptance criteria:

- Reproduce current Chroma advisories from current audit data.
- Keep Chroma out of default production dependencies while unresolved upstream risk exists.
- Evaluate splitting `vectorstores` into granular `qdrant` and `chroma` extras while preserving an aggregate compatibility extra where practical.
- Verify install/import behavior.
- Do not silently remove Chroma functionality or claim unresolved risk is fixed.

## REQ-SQDH-DEPS-004 — Improve optional-extra CI evidence

Acceptance criteria:

- Optional-extra audits remain visibly separate from the default dependency gate.
- Fixable HIGH/CRITICAL findings are remediated.
- Unfixable upstream advisories remain explicit.
- No broad advisory suppression is introduced.

## REQ-SQDH-AUDIT-001 — Full repository re-audit

Re-audit code, tests, CI, deployment assets, and operational configuration for:

- tenant isolation
- authentication and authorization
- API keys
- SSRF
- rate limiting and trusted proxy behavior
- CORS and upload limits
- Redis and FAISS persistence
- tar restore
- alert expression evaluation
- dependency locking and optional dependencies
- Docker/runtime user
- CI blocking semantics
- docs/code consistency
- deploy scripts and health scripts
- observability and Prometheus references
- stale/dead files and scripts
- production/test coupling

README or other documentation claims are not sufficient evidence by themselves.

## REQ-SQDH-AUDIT-002 — Evidence-grade findings

Every finding must use one evidence grade:

- Verified by executed test
- Verified by static code inspection
- Verified by CI
- Not reproduced / needs environment
- Historical / no longer present

Allowed statuses:

- OPEN
- FIXED
- ACCEPTED-UPSTREAM-RISK
- NOT-REPRODUCED
- HISTORICAL-RESOLVED
- NEEDS-ENVIRONMENT

## Preserved Phase 3.5 invariants

- Tenant authorization remains fail-closed.
- Production code does not couple authorization to test doubles.
- Runtime Redis/FAISS document pickle deserialization is not reintroduced.
- Python `eval` is not reintroduced for alert evaluation.
- Tar restore remains traversal/link/device safe.
- Bandit HIGH/MEDIUM remains blocking and LOW remains visible.
- Security Regression Suite remains zero-skip/xfail.
- `uv.lock` remains authoritative.
- `requirements.txt` remains generated.
- Default production dependency risk stays separate from optional-extra risk.
- Container remains non-root.
- The user-owned `.cursorignore` deletion is never restored, staged, or committed by Phase 4.
