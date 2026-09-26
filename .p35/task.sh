#!/usr/bin/env bash
# Temporary Phase 3.5 workspace task B1: apply the security fixes, run the checks,
# and run the new regression tests against main (red) and the change (green).
set -uo pipefail
R="$GITHUB_WORKSPACE/results"
WS="$GITHUB_WORKSPACE/ws/.p35"
cd "$GITHUB_WORKSPACE"
git clone -q "https://github.com/${GITHUB_REPOSITORY}.git" repo
cd repo
git checkout -q -b phase3-5/security-hardening
cp -R "$WS/files/." .
if ! python3.12 "$WS/tools/apply_edits.py" . "$WS"/edits/*.edits > "$R/10-apply.txt" 2>&1; then
  echo "edits failed"
  exit 1
fi
python3.12 -m compileall -q ragbot tests scripts > "$R/11-compile.txt" 2>&1
echo "compile exit=$?" >> "$R/11-compile.txt"
git add -A
git status --short > "$R/12-status.txt"

python3.12 -m venv /tmp/v312
PY=/tmp/v312/bin/python
$PY -m pip -q install --upgrade pip > /dev/null 2>&1
{ $PY -m pip -q install -r requirements.txt && $PY -m pip -q install -e ".[dev]"; } > "$R/20-install.txt" 2>&1
echo "install exit=$?" >> "$R/20-install.txt"

$PY -m bandit -c pyproject.toml -r ragbot -f json -q -o /tmp/bandit.json
echo "bandit exit=$?" > "$R/30-bandit.txt"
python3.12 "$WS/tools/bandit_render.py" /tmp/bandit.json "$PWD" --summary-only >> "$R/30-bandit.txt" 2>&1

$PY -m pytest tests/security/test_phase35_*.py -q -p no:cacheprovider --no-cov --tb=short -rfE > "$R/40-new-tests.txt" 2>&1
echo "exit=$?" >> "$R/40-new-tests.txt"

$PY scripts/verification/run_suite.py security --update-manifest > "$R/41-manifest.txt" 2>&1
echo "exit=$?" >> "$R/41-manifest.txt"
git diff --stat -- tests/security/suite_manifest.json >> "$R/41-manifest.txt"

$PY scripts/verification/run_suite.py security --report /tmp/security.json -- -q -p no:cacheprovider > /tmp/security.log 2>&1
echo "exit=$?" > "$R/50-security.txt"
python3.12 "$WS/tools/report_digest.py" /tmp/security.json >> "$R/50-security.txt" 2>&1
$PY scripts/verification/run_suite.py full --report /tmp/full.json -- -q -p no:cacheprovider > /tmp/full.log 2>&1
echo "exit=$?" > "$R/51-full.txt"
python3.12 "$WS/tools/report_digest.py" /tmp/full.json >> "$R/51-full.txt" 2>&1
tail -c 8000 /tmp/full.log > "$R/52-full-tail.txt"

# Red run: the new regression tests against the code of main
git worktree add -q /tmp/main-wt main
cp tests/security/test_phase35_*.py /tmp/main-wt/tests/security/
(
  cd /tmp/main-wt &&
  PYTHONPATH=/tmp/main-wt $PY -c "import ragbot; print('ragbot from', ragbot.__file__)" &&
  PYTHONPATH=/tmp/main-wt $PY -m pytest tests/security/test_phase35_*.py -q -p no:cacheprovider --no-cov -o addopts="" --tb=no -rfE
) > "$R/60-red-on-main.txt" 2>&1
echo "exit=$?" >> "$R/60-red-on-main.txt"

git add -A
git diff --cached --stat > "$R/70-diffstat.txt"
git diff --cached -- ragbot pyproject.toml > "$R/71-diff-ragbot.txt"
git diff --cached -- tests/security/conftest.py tests/integration tests/unit > "$R/72-diff-tests.txt"
echo done
