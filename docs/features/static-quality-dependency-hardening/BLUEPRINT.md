# Phase 4 — Static Quality & Dependency Hardening — Blueprint

## Feature Summary

Phase 4 converts accumulated static-analysis debt into enforceable quality gates, improves optional dependency security evidence, and performs a fresh code-first repository re-audit before larger application features resume.

The phase is sequential:

1. Ruff debt cleanup and gate promotion.
2. MyPy debt cleanup and gate promotion.
3. Optional dependency security and extra architecture.
4. Full repository re-audit and documentation synchronization.

The starting branch is `phase4/static-quality-dependency-hardening` from commit `ce257dcf32e189a01706386a708ed4f2f6ab973b`. The fresh Ruff baseline is 4640 findings. MyPy is intentionally not re-baselined until Ruff reaches zero, preserving the required phase order.

## Component Blueprint Composition

### Verification Pipeline

The existing GitHub Actions verification workflow is the integration point for full tests, the security suite, static analysis, dependency audits, optional-extra audits, container verification, and the final Verification Summary. Phase 4 changes only policy needed to promote Ruff and MyPy after each is independently green.

### Security Regression Suite

The security suite remains a non-negotiable regression boundary. Any quality refactor touching auth, tenant isolation, persistence, API behavior, archive restore, alert evaluation, or other security-sensitive code must run relevant security coverage.

### Static Analysis runner

`scripts/verification/static_analysis.py` remains the canonical static-check wrapper. Ruff currently checks `.`; MyPy checks `ragbot` with the repository configuration and missing third-party imports ignored at invocation level; Bandit keeps its existing HIGH/MEDIUM blocking semantics.

Phase 4 must not create a second conflicting static-analysis path.

### Dependency Audit runner

`scripts/verification/dependency_audit.py` remains the canonical audit implementation. Default production and optional extras remain separate security postures.

### Verification Summary

`scripts/verification/summary.py` remains the merge-policy summary. It must classify Ruff and MyPy as blocking only after they are individually green and promoted.

### Branch Protection / required checks

At preflight, `main` requires the Python 3.10/3.11/3.12 test jobs, the three security-suite jobs, Dependency Vulnerability Check, Container Build Check, and Verification Summary. Ruff and MyPy are not yet required checks.

Phase 4 must verify the actual post-promotion check names before updating required-check policy.

### Locked dependency graph

`pyproject.toml` is the dependency declaration source, `uv.lock` is the authoritative transitive lock, and `requirements.txt` is a generated production export. Phase 4 never hand-edits the generated export.

### Ali Computer Agent local development workflow

All repository inspection, edits, tests, git status/diff/staging, and commits are executed against `F:\tenant-rag` using Ali Computer Agent. GitHub is used for remote state, PRs, Actions evidence, branch protection, and merge operations.

The existing `F:\tenant-rag\venv` is preserved. The pre-existing unstaged deletion of `.cursorignore` is user-owned and excluded from all Phase 4 commits.

## Feature-Specific Components

### RuffDebtRemediator

A process component that inventories Ruff findings, applies reviewed safe fixes in batches, performs manual semantic remediation, and records before/after evidence.

### TypeDebtRemediator

A process component activated after Ruff is green. It groups MyPy failures by error family/module, applies explicit first-party type modeling, and avoids broad `Any`/ignore escapes.

### OptionalExtraAuditor

A tooling/process component that resolves each declared extra from the frozen lock, audits it independently, records package/advisory counts, and traces vulnerable transitives.

### QualityGatePolicy

The policy layer represented by workflow mode, summary classification, and branch required-checks. It promotes Ruff/MyPy only after green evidence and never weakens Bandit or dependency gates.

### RepositoryReAudit

A code-first inspection and verification pass across security invariants, deployment assets, observability, scripts, docs, and CI semantics.

### AuditEvidenceRecorder

The documentation process that records each re-audit finding with severity, status, evidence grade, location, reproduction, fix/test status, and residual risk.

## System Contracts

### Key Contracts

- Tenant authorization fails closed.
- No runtime pickle deserialization is reintroduced for Redis or FAISS document metadata.
- No Python `eval` is reintroduced for alert expressions.
- Safe tar extraction remains enforced.
- Bandit HIGH/MEDIUM remains blocking.
- Security Regression Suite remains zero-skip/xfail.
- `uv.lock` remains authoritative.
- `requirements.txt` remains generated.
- Default production dependencies remain isolated from optional-extra risk.
- Ruff/MyPy become blocking only after green evidence.
- Quality debt is not hidden by weakening configuration.
- User pre-existing local changes are not touched.

### Integration Contracts

#### Ruff invocation contract

Canonical configured scope: `ruff check . --no-fix`, using the pinned dev version. Safe fixes are applied only in reviewed batches. Final configured result must be zero.

#### MyPy invocation contract

Canonical CI-equivalent target: `mypy ragbot --ignore-missing-imports --no-color-output --no-pretty`, using the repository MyPy configuration. Fresh baseline occurs after Ruff reaches zero.

#### Dependency audit contract

Default production dependency audit remains blocking and lock-driven. Optional extra audits are independent and may remain report-only only for explicitly documented upstream risk.

#### Optional-extra matrix contract

The CI matrix must reflect the actual extras declared by `pyproject.toml`; any new granular `qdrant`/`chroma` extras must be reflected in audit coverage.

#### CI Summary contract

Verification Summary must fail when any blocking job fails and must distinguish report-only optional-risk evidence from blocking default-production checks.

#### PR / required-check contract

Required status checks are updated only after the exact GitHub check names are observed on the PR. No merge occurs with a red blocking check.

#### Local Windows verification contract

Local iterative verification uses `F:\tenant-rag\venv\Scripts\python.exe` on Python 3.12.8. Python 3.10/3.11 claims come only from real environments or GitHub Actions.

## Architecture Decision Records

### ADR-001: Resolve debt instead of baselining thousands of ignores

**Context:** The fresh Ruff baseline contains 4640 findings, with most debt concentrated in modernization and formatting families but also real correctness findings.

**Decision:** Remediate the configured debt instead of adding global suppressions, exclusions, or ignore baselines.

**Consequences:** The diff may be broad, so changes are split into reviewed mechanical and semantic batches with tests between meaningful batches.

### ADR-002: Ruff becomes blocking only after zero configured violations

**Context:** Ruff is currently report-only.

**Decision:** Keep Ruff report-only during remediation. Promote it only after the configured scope reaches zero locally and is proven green in CI.

**Consequences:** Branch protection changes happen after the stable blocking check name is observed.

### ADR-003: MyPy becomes blocking only after project errors are resolved

**Context:** MyPy is currently report-only and the phase order requires its fresh baseline after Ruff is green.

**Decision:** Do not weaken MyPy globally. Re-baseline after Ruff, remediate first-party errors, then promote.

**Consequences:** No current MyPy count is claimed before the required baseline run.

### ADR-004: Optional dependency risks stay separate from hardened default production

**Context:** Optional backends can carry advisories that are irrelevant to the default production environment.

**Decision:** Audit each extra independently without weakening the default gate.

**Consequences:** Optional upstream risk stays visible without contaminating the security claim for the default install.

### ADR-005: Chroma remains optional while unresolved upstream advisories exist

**Context:** Phase 3.5 recorded unresolved Chroma advisories in optional environments.

**Decision:** Reproduce current evidence before changing dependencies. Do not move Chroma into default production. Evaluate granular extras so Qdrant-only users need not install Chroma.

**Consequences:** Backwards compatibility may be preserved through an aggregate `vectorstores` extra while safer granular extras are introduced if current evidence supports the change.

### ADR-006: Re-audit uses code/test/CI evidence, not documentation claims

**Context:** Repository documentation may lag implementation.

**Decision:** Every current finding is grounded in executed tests, static code inspection, CI evidence, or explicitly marked environment limitations.

**Consequences:** Historical findings are not re-labeled as current without reproduction.

### ADR-007: Local edits are made through Ali Computer Agent against the user's checkout

**Context:** The authoritative development copy is the user's Windows checkout.

**Decision:** Source edits, verification, and git operations are local through Ali Computer Agent; GitHub APIs are reserved for remote/PR/CI concerns.

**Consequences:** The user's `venv` and unrelated workspace changes remain under user control.
