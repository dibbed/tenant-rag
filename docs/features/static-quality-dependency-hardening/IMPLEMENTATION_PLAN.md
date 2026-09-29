# Phase 4 — Static Quality & Dependency Hardening — Implementation Plan

## Working rules

- Branch: `phase4/static-quality-dependency-hardening`
- Baseline: `ce257dcf32e189a01706386a708ed4f2f6ab973b`
- Local Python: 3.12.8 in `F:\tenant-rag\venv`
- Never stage `.cursorignore`.
- Use explicit path staging only.
- Do not weaken Phase 3.5 security gates.
- Keep each meaningful batch inspectable and testable.

## 1. Local preflight

**Scope:** repository metadata, environment, CI/verification assets.  
**Checks:** repository exists; local/remote HEAD; workspace; `.cursorignore`; interpreter; Python version; `pip check`; lock/export files; workflow; verification scripts; security manifest.  
**Rollback/verification:** no mutation except remote fetch and locked dev-tool install into the existing venv.  
**Behavior:** none.

Status: completed. Local/remote main both matched `ce257dcf...`; only pre-existing `.cursorignore` deletion was present.

## 2. Fresh baseline capture

**Scope:** configured static-analysis tools and current dependency declarations.  
**Checks:** capture Ruff now; capture MyPy only after Ruff green; re-read optional extras before dependency audit.  
**Rollback/verification:** temporary artifacts are deleted before commit.  
**Behavior:** none.

Ruff baseline: 4640 findings.

## 3. Ruff inventory

**Scope:** entire configured Ruff target.  
**Checks:** group by rule, repository area, and high-density files.  
**Rollback/verification:** inventory is documentation only.  
**Behavior:** none.

## 4. Ruff safe fixes

**Scope:** import ordering, whitespace, deprecated typing syntax, safe modernization, redundant f prefixes, quote normalization, and other Ruff-declared safe fixes.  
**Commands/checks:** apply fixes in explicit rule-family batches; inspect diff; rerun Ruff; run affected tests where executable code changes.  
**Rollback/verification:** use surgical rollback if a batch changes semantics or breaks tests.  
**Behavior:** intended style/typing-syntax only.

## 5. Ruff manual semantic fixes

**Scope:** remaining F/B/SIM/PERF/RUF/ARG and similar findings requiring intent review.  
**Commands/checks:** inspect each family and high-density module; use targeted edits; run affected tests and security tests for sensitive modules.  
**Rollback/verification:** no finding is fixed by behavior change without regression coverage.  
**Behavior:** no intentional runtime change unless fixing an actual bug with tests.

## 6. Ruff gate promotion

**Scope:** `.github/workflows/ci.yml`, summary/policy tests, relevant docs.  
**Checks:** zero Ruff findings locally; CI report-mode green; then mode -> blocking; verify check name.  
**Rollback/verification:** do not modify required checks until stable PR evidence exists.  
**Behavior:** CI policy only.

## 7. MyPy inventory

**Scope:** `ragbot` configured target.  
**Checks:** run CI-equivalent invocation after Ruff green; group by code, file, architecture, and third-party vs first-party root cause.  
**Rollback/verification:** inventory only.  
**Behavior:** none.

## 8. MyPy fixes by error family

**Scope:** first-party modules with typing errors.  
**Checks:** repair in module/error-family batches; rerun MyPy and affected pytest; security suite for sensitive areas.  
**Rollback/verification:** no global weakening or mass ignores.  
**Behavior:** typing/modeling only unless an actual bug is exposed, then add regression coverage.

## 9. MyPy gate promotion

**Scope:** workflow, summary/policy tests, required-check policy after stable evidence.  
**Checks:** zero project errors locally; green CI; promote to blocking; verify exact check name.  
**Rollback/verification:** keep report-only until green.  
**Behavior:** CI policy only.

## 10. Optional extras resolution/audit

**Scope:** every extra currently declared in `pyproject.toml`.  
**Checks:** frozen-lock install/audit per extra, package/severity counts, import/smoke coverage, parent tracing.  
**Rollback/verification:** default production gate must remain clean.  
**Behavior:** dependency/tooling only unless extra architecture changes.

## 11. Protobuf investigation/remediation

**Scope:** extras/dependency parents that resolve protobuf.  
**Checks:** reproduce advisory; identify constraints; verify fixed-version compatibility; update `pyproject.toml`/lock only if safe.  
**Rollback/verification:** affected extra tests plus default dependency gate.  
**Behavior:** dependency versions only.

## 12. Chroma extra architecture review

**Scope:** `full`/`vectorstores`, Chroma/Qdrant imports, docs, CI matrix.  
**Checks:** reproduce Chroma advisories; evaluate granular `qdrant` and `chroma` extras with aggregate compatibility extra.  
**Rollback/verification:** preserve Chroma functionality; verify Qdrant-only installation avoids Chroma if split is adopted.  
**Behavior:** packaging/install surface, not runtime semantics.

## 13. Full repo re-audit

**Scope:** security boundaries, persistence, CI, Docker/deploy, observability, docs/code consistency, stale artifacts and scripts.  
**Checks:** code-first inspection plus targeted tests/CI evidence.  
**Deliverable:** `docs/security/PHASE4_FULL_REAUDIT.md`.  
**Rollback/verification:** critical/high regressions found are fixed in Phase 4 with tests; medium/low out-of-scope architecture work is documented.  
**Behavior:** only verified regression fixes.

## 14. Documentation sync

**Scope:** README, README.fa, SECURITY, CONTRIBUTING, testing docs, verification-pipeline docs, Phase 4 docs, vectorstore/dependency docs.  
**Checks:** update only verified facts and final counts.  
**Behavior:** documentation only.

## 15. Full local verification

Run as supported on Windows:

- full Ruff
- full MyPy
- Bandit gate
- default dependency gate
- optional-extra audit tooling
- full pytest on Python 3.12
- Security Regression Suite
- lock/export drift verification
- container verification only if Docker is available

Do not claim unavailable Python versions or Docker success.

## 16. PR creation

Push the feature branch and open PR to `main` titled `Complete static quality and dependency hardening`.

PR description includes baseline, Ruff/MyPy before/after, policy changes, optional dependency evidence, protobuf/Chroma results, test results, re-audit summary, residual risks, and explicit `.cursorignore` exclusion.

## 17. GitHub CI verification

Verify the real PR matrix:

- Tests 3.10/3.11/3.12
- Security Regression Suite 3.10/3.11/3.12
- Bandit blocking
- Ruff blocking
- MyPy blocking
- Default Dependency Vulnerability Check
- Container Build Check
- Verification Summary

## 18. Merge only after all blockers are green

Use squash merge unless repository state gives a concrete reason otherwise. Never merge a red blocker.

## 19. Main post-merge verification

Verify the resulting `main` commit and the real post-merge workflow. Record final SHA, run, required checks, and branch cleanup state in `FINAL_REPORT.md`.
