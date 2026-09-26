"""Temporary Phase 3.5 workspace tool: print a run_suite.py report."""

import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
print("status:", report.get("status"), "| summary:", report.get("summary"))
print("counts:", report.get("counts"), "| duration:", report.get("duration_seconds"), "| python:", report.get("python"))
for problem in report.get("problems", []):
    print("problem:", problem)
for item in report.get("failed_tests", []):
    print("FAILED", item.get("nodeid"), "::", (item.get("message") or "")[:1200])
for item in report.get("collection_problems", []):
    print("COLLECTION", str(item)[:1200])
for item in report.get("skipped_tests", []):
    print("skipped", item.get("nodeid"), "::", item.get("reason"))
manifest = report.get("manifest") or {}
if manifest:
    print("manifest:", {key: manifest.get(key) for key in ("expected", "missing", "unexpected", "added_vs_base", "removed_vs_base")})
