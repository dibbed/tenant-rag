#!/usr/bin/env bash
# verify_baseline.sh - Run the repository's existing verification checks in a
# repeatable way and print a status summary.
#
# Audit and measurement only. This script does not modify tracked files, does
# not fix anything, and does not install packages unless --install is given.
#
# Usage:
#   bash scripts/verify_baseline.sh [--install] [--skip-docker] [--skip-tests]
#
#   --install      Run the same install steps as .github/workflows/ci.yml first
#   --skip-docker  Do not run docker build / docker compose config
#   --skip-tests   Do not run pytest (coverage is then skipped too)
#
# Environment:
#   PYTHON            Interpreter to use (default: python3, else python)
#   BASELINE_OUT_DIR  Log directory (default: $TMPDIR/tenant-rag-baseline-<timestamp>)
#
# Exit code: 0 when no check FAILED (SKIPPED and INFO do not fail), 1 otherwise.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR" || exit 1

INSTALL=0
SKIP_DOCKER=0
SKIP_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --install) INSTALL=1 ;;
    --skip-docker) SKIP_DOCKER=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${BASELINE_OUT_DIR:-${TMPDIR:-/tmp}/tenant-rag-baseline-$TIMESTAMP}"
mkdir -p "$OUT_DIR" || exit 1

if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

# CPU isolation, same as .github/workflows/ci.yml and README
export CUDA_VISIBLE_DEVICES=""
export TORCH_DEVICE="cpu"

RESULTS=()
FAILED=0

# record <name> <status> <detail>
record() {
  RESULTS+=("$1|$2|$3")
  if [ "$2" = "FAIL" ]; then
    FAILED=$((FAILED + 1))
  fi
  printf '[%s] %s - %s\n' "$2" "$1" "$3"
}

# run_check <name> <logfile> <command...>
run_check() {
  local name="$1"
  local log="$OUT_DIR/$2"
  shift 2
  echo "+ $*" > "$log"
  "$@" >> "$log" 2>&1
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    record "$name" "PASS" "exit 0 (log: $log)"
  else
    record "$name" "FAIL" "exit $rc (log: $log)"
  fi
  return "$rc"
}

has_module() {
  "$PY" -c "import $1" >/dev/null 2>&1
}

install_deps() {
  "$PY" -m pip install --upgrade pip &&
    "$PY" -m pip install -r requirements.txt &&
    "$PY" -m pip install -e ".[dev]"
}

check_shell_syntax() {
  local rc=0
  local f
  for f in scripts/*.sh; do
    [ -f "$f" ] || continue
    echo "bash -n $f"
    bash -n "$f" || rc=1
  done
  return "$rc"
}

echo "== TenantRAG baseline verification =="
echo "Project: $PROJECT_DIR"
echo "Commit:  $(git rev-parse HEAD 2>/dev/null || echo unknown)"
echo "Logs:    $OUT_DIR"
echo

# 1. Python version
if command -v "$PY" >/dev/null 2>&1; then
  record "Python version" "INFO" "$("$PY" --version 2>&1)"
else
  record "Python version" "FAIL" "interpreter '$PY' not found"
fi

# 2. Dependency installation (optional) and consistency
if [ "$INSTALL" -eq 1 ]; then
  run_check "Dependency install (CI steps)" install.log install_deps
else
  record "Dependency install (CI steps)" "SKIPPED" "pass --install to run the CI install steps"
fi
run_check "Dependency consistency (pip check)" pip_check.log "$PY" -m pip check

# 3. Tests (coverage is produced by pyproject addopts)
if [ "$SKIP_TESTS" -eq 1 ]; then
  record "Tests (pytest)" "SKIPPED" "--skip-tests"
elif has_module pytest; then
  run_check "Tests (pytest)" pytest.log "$PY" -m pytest -q -rs --junitxml="$OUT_DIR/junit.xml"
  summary="$(grep -E '[0-9]+ (passed|failed|error)' "$OUT_DIR/pytest.log" | tail -n 1)"
  record "Test summary" "INFO" "${summary:-no pytest summary line found}"
else
  record "Tests (pytest)" "SKIPPED" "pytest not installed"
fi

# 4. Coverage (only if coverage.xml was written during this run)
if [ "$SKIP_TESTS" -eq 0 ] && [ -f coverage.xml ] && [ coverage.xml -nt "$OUT_DIR" ]; then
  cov="$("$PY" - <<'PYEOF'
import xml.etree.ElementTree as ET
root = ET.parse("coverage.xml").getroot()
rate = float(root.get("line-rate", 0)) * 100
print(f"{rate:.1f}% line coverage (pyproject omit list applies)")
PYEOF
)"
  record "Coverage" "INFO" "$cov"
else
  record "Coverage" "SKIPPED" "coverage.xml not produced in this run"
fi

# 5. Lint (no fixes applied)
if has_module ruff; then
  run_check "Lint (ruff check)" ruff_check.log "$PY" -m ruff check . --no-fix --statistics
else
  record "Lint (ruff check)" "SKIPPED" "ruff not installed"
fi

# 6. Formatting (check only)
if has_module ruff; then
  run_check "Formatting (ruff format --check)" ruff_format.log "$PY" -m ruff format --check .
else
  record "Formatting (ruff format --check)" "SKIPPED" "ruff not installed"
fi

# 7. Type checking (same command as `make type-check`)
if has_module mypy; then
  run_check "Type checking (mypy)" mypy.log "$PY" -m mypy ragbot --ignore-missing-imports
  mypy_summary="$(grep -E '^(Found [0-9]+ error|Success:)' "$OUT_DIR/mypy.log" | tail -n 1)"
  record "MyPy summary" "INFO" "${mypy_summary:-no mypy summary line found}"
else
  record "Type checking (mypy)" "SKIPPED" "mypy not installed"
fi

# 8. Security scan (same scope as `make security`)
if has_module bandit; then
  run_check "Security scan (bandit)" bandit.log "$PY" -m bandit -q -r ragbot
else
  record "Security scan (bandit)" "SKIPPED" "bandit not installed"
fi

# 9. Shell script syntax
run_check "Shell syntax (bash -n scripts/*.sh)" shell_syntax.log check_shell_syntax

# 10. Docker build and compose validation
if [ "$SKIP_DOCKER" -eq 1 ]; then
  record "Docker build" "SKIPPED" "--skip-docker"
  record "Docker compose config" "SKIPPED" "--skip-docker"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  run_check "Docker build" docker_build.log docker build -t tenant-rag:baseline .
  if docker compose version >/dev/null 2>&1; then
    run_check "Docker compose config" compose_config.log docker compose -f docker-compose.yml config -q
  elif command -v docker-compose >/dev/null 2>&1; then
    run_check "Docker compose config" compose_config.log docker-compose -f docker-compose.yml config -q
  else
    record "Docker compose config" "SKIPPED" "docker compose not available"
  fi
  if [ ! -f .env ]; then
    record "Compose note" "INFO" "docker-compose.yml requires .env (env_file); none present"
  fi
else
  record "Docker build" "SKIPPED" "docker not available or daemon not running"
  record "Docker compose config" "SKIPPED" "docker not available or daemon not running"
fi

# Summary
{
  echo "# Baseline verification summary"
  echo
  echo "- Commit: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "- Run: $TIMESTAMP"
  echo
  echo "| Check | Status | Details |"
  echo "|---|---|---|"
  for r in "${RESULTS[@]}"; do
    IFS='|' read -r n s d <<< "$r"
    echo "| $n | $s | $d |"
  done
} > "$OUT_DIR/summary.md"

echo
echo "== Summary =="
printf '%-38s %-8s %s\n' "Check" "Status" "Details"
for r in "${RESULTS[@]}"; do
  IFS='|' read -r n s d <<< "$r"
  printf '%-38s %-8s %s\n' "$n" "$s" "$d"
done
echo
echo "Summary table: $OUT_DIR/summary.md"

if [ "$FAILED" -eq 0 ]; then
  exit 0
fi
echo "$FAILED check(s) failed."
exit 1
