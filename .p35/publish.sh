#!/usr/bin/env bash
# Temporary Phase 3.5 workspace: publish the results as small text parts on tmp/p35-results.
set -euo pipefail
results="$1"
out="$(mktemp -d)"
mkdir -p "$out/r"
cd "$results"
find . -type f -print | LC_ALL=C sort | while IFS= read -r f; do
  name="${f#./}"
  safe="$(printf '%s' "$name" | tr '/' '_')"
  if [ -s "$f" ]; then
    split -C 11000 -d -a 3 "$f" "$out/r/${safe}."
  else
    : > "$out/r/${safe}.empty"
  fi
done
cd "$out"
( cd r && ls -1 | LC_ALL=C sort | nl -ba ) > "r/!index.txt"
git init -q
git config user.name "p35-workspace"
git config user.email "p35-workspace@users.noreply.github.com"
git commit -q --allow-empty -m "p35 results base"
git add r
git commit -q -m "p35 results: run ${GITHUB_RUN_ID} (${GITHUB_SHA:0:12})"
git push -q -f "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" HEAD:refs/heads/tmp/p35-results
echo "published $(ls r | wc -l) parts"
