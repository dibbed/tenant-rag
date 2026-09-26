#!/usr/bin/env bash
# Temporary Phase 3.5 workspace task A1: baseline of main.
set -uo pipefail
R="$GITHUB_WORKSPACE/results"
WS="$GITHUB_WORKSPACE/ws/.p35"
cd "$GITHUB_WORKSPACE"
git clone -q "https://github.com/${GITHUB_REPOSITORY}.git" repo
cd repo
{ git log -1 --format='%H %ad %s'; python3.10 --version; python3.11 --version; python3.12 --version; } > "$R/00-head.txt" 2>&1

{
  echo "===== Makefile (cat -nT: a tab is shown as ^I)"; cat -nT Makefile
  for f in Dockerfile .dockerignore docker-compose.yml requirements.txt requirements-optional.txt requirements-stable.txt scripts/verify_pipeline.sh scripts/verification/requirements-audit.txt .gitignore; do
    echo "===== $f"; cat -n "$f"
  done
} > "$R/10-build-files.txt" 2>&1
cat -n pyproject.toml > "$R/11-pyproject.txt" 2>&1
{
  echo "== tracked files with CRLF"; git grep -Il $'\r' || true
  echo "== tracked py/sh/yml/toml/json files with tabs"; git grep -Il $'\t' -- '*.py' '*.sh' '*.yml' '*.yaml' '*.toml' '*.json' || true
} > "$R/12-whitespace.txt" 2>&1
git ls-files > "$R/13-ls-files.txt"
{ echo "== docs"; find docs -type f | LC_ALL=C sort; echo "== scripts"; find scripts -type f | LC_ALL=C sort; echo "== .github"; find .github -type f | LC_ALL=C sort; } > "$R/14-trees.txt" 2>&1
{
  find tests -maxdepth 2 -type d | LC_ALL=C sort
  echo "== tests/security"; ls -1 tests/security
  echo "== suite manifest (first 4000 bytes)"; head -c 4000 tests/security/suite_manifest.json; echo
} > "$R/15-tests.txt" 2>&1

# Bandit as in CI: the pinned bandit of the dev extra, bandit -c pyproject.toml -r ragbot
python3.12 -m venv /tmp/venv-bandit
/tmp/venv-bandit/bin/python -m pip -q install "$(python3.12 scripts/verification/static_analysis.py pins bandit)" > "$R/20-bandit-run.txt" 2>&1
/tmp/venv-bandit/bin/bandit --version >> "$R/20-bandit-run.txt" 2>&1
/tmp/venv-bandit/bin/bandit -c pyproject.toml -r ragbot -f json -q -o /tmp/bandit-ragbot.json; echo "ragbot scan exit=$?" >> "$R/20-bandit-run.txt"
python3.12 "$WS/tools/bandit_render.py" /tmp/bandit-ragbot.json "$PWD" > "$R/21-bandit-ragbot.txt" 2>&1
/tmp/venv-bandit/bin/bandit -r . -x ./.git,./tests -f json -q -o /tmp/bandit-repo.json; echo "repo scan without tests exit=$?" >> "$R/20-bandit-run.txt"
python3.12 "$WS/tools/bandit_render.py" /tmp/bandit-repo.json "$PWD" --summary-only > "$R/22-bandit-repo-summary.txt" 2>&1

{
  echo "== md5 in code"; git grep -n -I -i 'md5' -- '*.py' '*.sh' '*.toml' '*.yml' 'Makefile' 'Dockerfile' || true
  echo "== md5 mentions in docs (count per file)"; git grep -c -I -i 'md5' -- '*.md' || true
  echo "== pickle"; git grep -n -I -E 'pickle|cloudpickle|\bdill\b|joblib|\.pkl\b' -- '*.py' '*.sh' '*.toml' '*.yml' || true
  echo "== eval/exec"; git grep -n -I -E '(^|[^.a-zA-Z_])(eval|exec)\(' -- '*.py' || true
  echo "== archives"; git grep -n -I -E 'extractall|tarfile|zipfile|unpack_archive' -- '*.py' '*.sh' || true
  echo "== mock in non-test code"; git grep -n -I -E 'unittest\.mock|MagicMock|AsyncMock|_mock_return_value' -- '*.py' ':!tests/**' || true
  echo "== nosec or noqa S"; git grep -n -I -E 'nosec|noqa: ?S[0-9]' || true
  echo "== usedforsecurity"; git grep -n -I 'usedforsecurity' || true
  echo "== hidden exit status in Makefile, shell scripts and workflows"; git grep -n -I -E '\|\| *true|\|\| *:|set \+e|continue-on-error|--exit-zero|exit 0' -- 'Makefile' '*.sh' '.github/**' || true
} > "$R/30-greps.txt" 2>&1

for f in ragbot/api/dependencies.py ragbot/caching/redis_cache.py ragbot/monitoring/alert_manager.py ragbot/security/secure_backup.py ragbot/rag/store/faiss_store.py; do
  cat -n "$f" > "$R/40-$(echo "$f" | tr '/' '_').txt" 2>&1
done

gh run download 36253494051 -R "$GITHUB_REPOSITORY" -D /tmp/reports-main > "$R/50-download.txt" 2>&1 || echo "download failed" >> "$R/50-download.txt"
python3.12 "$WS/tools/digest.py" /tmp/reports-main 700 > "$R/51-main-run-digest.txt" 2>&1
echo done
