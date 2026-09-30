#!/usr/bin/env bash
# verify_pipeline.sh - run the Verification Pipeline checks locally, with the same
# tools and policies as .github/workflows/ci.yml, and print the Verification Summary.
#
# Usage:
#   bash scripts/verify_pipeline.sh [CHECK ...]
#
# CHECK is one or more of (default: all):
#   tests      full test suite (Blocking)
#   security   Security Regression Suite: no failed or skipped test, and the
#              collected tests match tests/security/suite_manifest.json (Blocking).
#              The Redis tests need a Redis server and TEST_REDIS_URL, for
#              example TEST_REDIS_URL=redis://localhost:6379/15.
#   static     Ruff, MyPy, and Bandit (Blocking)
#   postgres   Alembic head + real PostgreSQL RLS/auth verification (Blocking)
#              Requires TEST_DATABASE_URL pointing to a disposable PostgreSQL DB.
#   deps       Locked default install + Dependency Vulnerability Check (Blocking)
#   container  Container Build Check: build, start, health, auth, non-root (Blocking, needs Docker)
#   all        every check above
#
# Environment:
#   PYTHON          interpreter with the project and its dev extra installed
#                   (default: python3, else python)
#   VERIFY_OUT_DIR  report directory (default: $TMPDIR/tenant-rag-verification-<timestamp>)
#   PIP_AUDIT       pip-audit executable. By default a virtual environment is created
#                   in $TMPDIR/tenant-rag-pip-audit from scripts/verification/requirements-audit.txt.
#   UV              uv executable used for dependency-lock verification (default: uv).
#
# Exit code: 0 when every Blocking Check that ran passed, 1 otherwise.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR" || exit 1

if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

CHECKS=("$@")
if [ "${#CHECKS[@]}" -eq 0 ]; then
  CHECKS=(all)
fi
for check in "${CHECKS[@]}"; do
  case "$check" in
    all|tests|security|static|postgres|deps|container) ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "Unknown check: $check (see --help)" >&2; exit 2 ;;
  esac
done

wants() {
  local check
  for check in "${CHECKS[@]}"; do
    if [ "$check" = "all" ] || [ "$check" = "$1" ]; then
      return 0
    fi
  done
  return 1
}

TMP_BASE="${TMPDIR:-/tmp}"
OUT="${VERIFY_OUT_DIR:-$TMP_BASE/tenant-rag-verification-$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT" || exit 1
export CUDA_VISIBLE_DEVICES=""
export TORCH_DEVICE="cpu"
VERSION="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')" || exit 1
BLOCKING_FAILED=0

blocking() {
  "$@" || BLOCKING_FAILED=1
}

if wants tests; then
  blocking "$PY" scripts/verification/run_suite.py full --report "$OUT/tests-py$VERSION.json"
fi

if wants security; then
  if [ -z "${TEST_REDIS_URL:-}" ]; then
    echo "note: TEST_REDIS_URL is not set, so the Redis rate limit tests are skipped and the Security Regression Suite fails." >&2
  fi
  blocking "$PY" scripts/verification/run_suite.py security --report "$OUT/security-py$VERSION.json"
fi

if wants static; then
  for tool in ruff mypy bandit; do
    blocking "$PY" scripts/verification/static_analysis.py "$tool" --mode blocking --report "$OUT/static-$tool.json"
  done
fi

if wants postgres; then
  if [ -z "${TEST_DATABASE_URL:-}" ]; then
    echo "error: TEST_DATABASE_URL is required for the PostgreSQL Verification check." >&2
    BLOCKING_FAILED=1
  else
    if ! DATABASE_URL="$TEST_DATABASE_URL" "$PY" -m alembic upgrade head; then
      BLOCKING_FAILED=1
    fi
    if TEST_DATABASE_URL="$TEST_DATABASE_URL" "$PY" -m pytest tests/postgres/test_phase5_postgres.py -v --tb=short --no-cov; then
      pg_status=0
    else
      pg_status=$?
    fi
    STATUS="$pg_status" REPORT_PATH="$OUT/postgresql.json" "$PY" - <<'PY'
import json
import os
from pathlib import Path

status = int(os.environ["STATUS"])
report = {
    "check": "postgresql",
    "title": "PostgreSQL Verification",
    "mode": "blocking",
    "status": "pass" if status == 0 else "fail",
    "summary": (
        "Alembic head plus real PostgreSQL RLS/auth verification passed"
        if status == 0
        else "Real PostgreSQL verification failed"
    ),
    "problems": [] if status == 0 else ["PostgreSQL pytest verification failed"],
}
path = Path(os.environ["REPORT_PATH"])
path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
PY
    if [ "$pg_status" -ne 0 ]; then
      BLOCKING_FAILED=1
    fi
  fi
fi

if wants deps; then
  UV_BIN="${UV:-uv}"
  if ! command -v "$UV_BIN" >/dev/null 2>&1; then
    echo "error: uv is required for locked dependency verification (install uv==0.12.19)" >&2
    BLOCKING_FAILED=1
  else
    blocking "$UV_BIN" lock --check
    LOCK_EXPORT="$OUT/requirements.locked.txt"
    blocking "$UV_BIN" export --frozen --no-emit-project --format requirements.txt --output-file "$LOCK_EXPORT"
    if ! diff -u <(tail -n +3 requirements.txt) <(tail -n +3 "$LOCK_EXPORT"); then
      echo "error: requirements.txt has drifted from uv.lock" >&2
      BLOCKING_FAILED=1
    fi

    LOCK_VENV="$TMP_BASE/tenant-rag-locked-default"
    rm -rf "$LOCK_VENV"
    if UV_PROJECT_ENVIRONMENT="$LOCK_VENV" "$UV_BIN" sync --frozen --no-install-project --python "$PY"; then
      AUDIT="${PIP_AUDIT:-}"
      if [ -z "$AUDIT" ]; then
        VENV="$TMP_BASE/tenant-rag-pip-audit"
        if [ ! -x "$VENV/bin/pip-audit" ]; then
          "$PY" -m venv "$VENV" &&
            "$VENV/bin/python" -m pip install --quiet --upgrade pip &&
            "$VENV/bin/python" -m pip install --quiet -r scripts/verification/requirements-audit.txt
        fi
        AUDIT="$VENV/bin/pip-audit"
      fi
      blocking "$PY" scripts/verification/dependency_audit.py run         --pip-audit "$AUDIT" --python "$LOCK_VENV/bin/python"         --report "$OUT/dependency-audit.json"
    else
      BLOCKING_FAILED=1
    fi
  fi
fi

if wants container; then
  blocking "$PY" scripts/verification/container_check.py --build --report "$OUT/container.json"
fi

blocking "$PY" scripts/verification/summary.py --reports "$OUT" --allow-missing \
  --python-versions "$VERSION" --output "$OUT/summary.md"
echo "Reports and summary: $OUT"
exit "$BLOCKING_FAILED"
