#!/usr/bin/env bash
# Temporary Phase 3.5 workspace task A2: uv lock prototype, extras export, exact dumps.
set -uo pipefail
R="$GITHUB_WORKSPACE/results"
WS="$GITHUB_WORKSPACE/ws/.p35"
cd "$GITHUB_WORKSPACE"
git clone -q "https://github.com/${GITHUB_REPOSITORY}.git" repo
cd repo
git log -1 --format='%H %s' > "$R/00-head.txt"

# Fresh main baseline (workflow_dispatch run of ci.yml)
gh run list -R "$GITHUB_REPOSITORY" --workflow ci.yml --branch main --limit 4 --json databaseId,event,status,conclusion,headSha,createdAt > "$R/01-main-runs.json" 2>&1
run_id="$(python3.12 -c 'import json,sys; runs=[r for r in json.load(open(sys.argv[1])) if r["event"]=="workflow_dispatch"]; print(runs[0]["databaseId"] if runs else "")' "$R/01-main-runs.json" 2>/dev/null)"
if [ -n "$run_id" ]; then
  gh run watch "$run_id" -R "$GITHUB_REPOSITORY" --interval 30 > /dev/null 2>&1 || true
  gh run view "$run_id" -R "$GITHUB_REPOSITORY" --json conclusion,event,headSha,jobs --jq '{conclusion, event, headSha, jobs: [.jobs[] | {name, conclusion}]}' > "$R/02-dispatch-run.json" 2>&1
  gh run download "$run_id" -R "$GITHUB_REPOSITORY" -D /tmp/reports-dispatch > /dev/null 2>&1 || echo "download failed" > "$R/02-download-error.txt"
  python3.12 "$WS/tools/digest.py" /tmp/reports-dispatch 300 > "$R/03-dispatch-digest.txt" 2>&1
fi

# uv lock prototype
python3.12 -m venv /tmp/uvenv
/tmp/uvenv/bin/python -m pip -q install --upgrade pip uv > /dev/null 2>&1
UV=/tmp/uvenv/bin/uv
{ "$UV" --version; /tmp/uvenv/bin/python -m pip index versions uv 2>/dev/null | head -2; } > "$R/60-uv.txt" 2>&1
for variant in A B; do
  dir="/tmp/lock$variant"
  mkdir -p "$dir"
  git archive HEAD | tar -x -C "$dir"
  if [ "$variant" = B ]; then
    printf '\n[tool.uv]\nenvironments = [\n    "python_version >= '"'"'3.10'"'"' and python_version < '"'"'3.13'"'"'",\n]\n' >> "$dir/pyproject.toml"
    tail -5 "$dir/pyproject.toml" >> "$R/61-lock-$variant.txt"
  fi
  start=$(date +%s)
  ( cd "$dir" && "$UV" lock ) >> "$R/61-lock-$variant.txt" 2>&1
  rc=$?
  echo "lock exit=$rc seconds=$(( $(date +%s) - start ))" >> "$R/61-lock-$variant.txt"
  if [ "$rc" -eq 0 ]; then
    echo "packages in uv.lock: $(grep -c '^\[\[package\]\]' "$dir/uv.lock")" >> "$R/61-lock-$variant.txt"
    echo "uv.lock bytes: $(wc -c < "$dir/uv.lock")" >> "$R/61-lock-$variant.txt"
    ( cd "$dir" && "$UV" lock --check ) >> "$R/61-lock-$variant.txt" 2>&1; echo "lock --check exit=$?" >> "$R/61-lock-$variant.txt"
    for extra in "" dev full offline ocr ml hf vectorstores docs test; do
      name="${extra:-default}"
      args=(export --frozen --format requirements.txt --no-emit-project --output-file "/tmp/req-$variant-$name.txt")
      [ -n "$extra" ] && args+=(--extra "$extra")
      ( cd "$dir" && "$UV" "${args[@]}" ) > /tmp/export.log 2>&1
      erc=$?
      pins=$(grep -cE '^[A-Za-z0-9_.-]+==' "/tmp/req-$variant-$name.txt" 2>/dev/null || echo 0)
      echo "export $name exit=$erc pins=$pins bytes=$(wc -c < "/tmp/req-$variant-$name.txt" 2>/dev/null || echo 0) $(tail -1 /tmp/export.log)" >> "$R/61-lock-$variant.txt"
    done
    head -c 3000 "/tmp/req-$variant-default.txt" > "$R/63-export-$variant-default-head.txt"
    grep -E '^(chromadb|llama-index|nltk|torch|numpy|onnxruntime|easyocr|google-cloud-vision|mkdocs-material)==' /tmp/req-$variant-*.txt > "$R/64-export-$variant-keypins.txt" 2>&1
  fi
done

# pip-audit in requirements mode on the default export (prototype for the extras audit)
python3.12 -m venv /tmp/auditenv
/tmp/auditenv/bin/python -m pip -q install -r scripts/verification/requirements-audit.txt > /dev/null 2>&1
for variant in A B; do
  f="/tmp/req-$variant-default.txt"
  [ -s "$f" ] || continue
  /tmp/auditenv/bin/pip-audit -r "$f" --no-deps --disable-pip -f json -o "/tmp/audit-$variant.json" --progress-spinner off > "$R/65-audit-$variant.txt" 2>&1
  echo "pip-audit exit=$?" >> "$R/65-audit-$variant.txt"
  python3.12 - "/tmp/audit-$variant.json" >> "$R/65-audit-$variant.txt" 2>&1 <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
deps = data.get("dependencies", [])
vulns = [(d["name"], d.get("version"), v["id"]) for d in deps for v in d.get("vulns", [])]
skipped = [(d["name"], d.get("skip_reason")) for d in deps if "skip_reason" in d]
print("dependencies:", len(deps), "vulns:", len(vulns), "skipped:", len(skipped))
for item in vulns: print("  vuln", *item)
for item in skipped[:20]: print("  skipped", *item)
EOF
done

# Exact dumps for the patches
{
  for f in ragbot/monitoring/alert_manager.py ragbot/main.py .env.test .github/dependency-audit-exceptions.json; do echo "===== $f"; cat -n "$f"; done
  echo "===== ragbot/outputs/health_endpoints.py 390-433"; sed -n '390,433p' ragbot/outputs/health_endpoints.py | cat -A | sed 's/\$$//' | head -60
} > "$R/70-dump-a.txt" 2>&1
{
  echo "===== secure_backup 1-30"; sed -n '1,30p' ragbot/security/secure_backup.py | cat -n
  echo "===== secure_backup 505-560"; awk 'NR>=505 && NR<=560 {printf "%6d\t%s\n", NR, $0}' ragbot/security/secure_backup.py
  echo "===== document_service 1-40"; awk 'NR<=40 {printf "%6d\t%s\n", NR, $0}' ragbot/services/document_service.py
  echo "===== document_service 244-250, 380-422"; awk '(NR>=244 && NR<=250) || (NR>=380 && NR<=422) {printf "%6d\t%s\n", NR, $0}' ragbot/services/document_service.py
  echo "===== semantic_chunker 700-715"; awk 'NR>=700 && NR<=715 {printf "%6d\t%s\n", NR, $0}' ragbot/rag/chunkers/semantic_chunker.py
  echo "===== token_chunker 525-545"; awk 'NR>=525 && NR<=545 {printf "%6d\t%s\n", NR, $0}' ragbot/rag/chunkers/token_chunker.py
  echo "===== embeddings/base 300-330"; awk 'NR>=300 && NR<=330 {printf "%6d\t%s\n", NR, $0}' ragbot/rag/embeddings/base.py
  echo "===== caching/base 215-265"; awk 'NR>=215 && NR<=265 {printf "%6d\t%s\n", NR, $0}' ragbot/caching/base.py
  echo "===== semantic_cache 1-30"; awk 'NR<=30 {printf "%6d\t%s\n", NR, $0}' ragbot/caching/semantic_cache.py
  echo "===== plugin_marketplace 1-30"; awk 'NR<=30 {printf "%6d\t%s\n", NR, $0}' ragbot/plugins/plugin_marketplace.py
  echo "===== faiss_store 1-35, 136-143, 686-732, 820-836, 1466-1476, 1505-1516"; awk '(NR<=35) || (NR>=136 && NR<=143) || (NR>=686 && NR<=732) || (NR>=820 && NR<=836) || (NR>=1466 && NR<=1476) || (NR>=1505 && NR<=1516) {printf "%6d\t%s\n", NR, $0}' ragbot/rag/store/faiss_store.py
  echo "===== ragbot/rag/store/__init__.py"; cat -n ragbot/rag/store/__init__.py | head -40
} > "$R/71-dump-b.txt" 2>&1
{
  echo "===== lines with trailing whitespace in files to patch (count)"
  for f in ragbot/monitoring/alert_manager.py ragbot/security/secure_backup.py ragbot/rag/store/faiss_store.py ragbot/services/document_service.py ragbot/caching/base.py ragbot/caching/semantic_cache.py ragbot/plugins/plugin_marketplace.py ragbot/rag/chunkers/semantic_chunker.py ragbot/rag/chunkers/token_chunker.py ragbot/rag/embeddings/base.py ragbot/rag/embeddings/st_embedder.py ragbot/main.py ragbot/outputs/health_endpoints.py scripts/verification/static_analysis.py scripts/verification/summary.py .github/workflows/ci.yml Makefile; do
    echo "$f: $(grep -c '[[:space:]]$' "$f")"
  done
  echo "===== paramiko or yaml.load users"; git grep -n -E 'paramiko|yaml\.load\(' -- '*.py' || true
  echo "===== docs mentioning requirements files, make lint/security, pip install"; git grep -n -E 'requirements(-stable|-optional)?\.txt|make (lint|security)|pip install -e|pip install -r' -- '*.md' 'Makefile' 'scripts/*.sh' 'Dockerfile' '.github/**' | head -120
} > "$R/72-dump-c.txt" 2>&1
cat -n scripts/verification/static_analysis.py > "$R/73-static_analysis.py.txt"
cat -n .github/workflows/ci.yml > "$R/74-ci.yml.txt"
cat -n docs/features/security-verification-pipeline/README.md > "$R/75-svp-readme.md.txt"
{ echo "===== CONTRIBUTING.md"; cat -n CONTRIBUTING.md; echo "===== CHANGELOG.md (head 60)"; head -60 CHANGELOG.md | cat -n; } > "$R/76-contrib-changelog.txt"
{ echo "===== SECURITY.md headings"; grep -n '^#' SECURITY.md; echo "===== SECURITY.md lines mentioning bandit, pickle, lock, chroma, verification"; grep -n -i -E 'bandit|pickle|lock|chroma|verification|report-only|blocking' SECURITY.md; } > "$R/77-security-md.txt" 2>&1
echo done
