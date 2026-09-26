"""Temporary Phase 3.5 workspace tool: render a Bandit JSON report compactly."""

import json
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1])
root = Path(sys.argv[2]).resolve()
summary_only = "--summary-only" in sys.argv
data = json.loads(path.read_text(encoding="utf-8"))
results = data.get("results", [])


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(root))
    except ValueError:
        return p


sev = Counter(r["issue_severity"] for r in results)
print(f"total={len(results)} " + " ".join(f"{k}={sev.get(k, 0)}" for k in ("HIGH", "MEDIUM", "LOW")))
print("errors:", data.get("errors"))
print("metrics_totals:", json.dumps(data.get("metrics", {}).get("_totals", {}), sort_keys=True))
print("== by test id and severity")
for (tid, name, s), n in sorted(Counter((r["test_id"], r["test_name"], r["issue_severity"]) for r in results).items()):
    print(f"  {tid} {name} {s}: {n}")
order = {"HIGH": 0, "MEDIUM": 1}
if summary_only:
    print("== HIGH/MEDIUM locations")
    for r in sorted((r for r in results if r["issue_severity"] in order), key=lambda r: (order[r["issue_severity"]], rel(r["filename"]), r["line_number"])):
        print(f"  {r['issue_severity']} {r['test_id']} {rel(r['filename'])}:{r['line_number']} {r['issue_text'][:90]}")
    sys.exit(0)
print("== HIGH and MEDIUM findings (with code)")
for r in sorted((r for r in results if r["issue_severity"] in order), key=lambda r: (order[r["issue_severity"]], rel(r["filename"]), r["line_number"])):
    print(f"-- {r['issue_severity']}/{r['issue_confidence']} {r['test_id']} {r['test_name']} {rel(r['filename'])}:{r['line_number']} range={r.get('line_range')}")
    print(f"   {r['issue_text']}")
    for line in (r.get("code") or "").rstrip("\n").splitlines():
        print(f"   | {line}")
print("== LOW findings (location only)")
for r in sorted((r for r in results if r["issue_severity"] == "LOW"), key=lambda r: (r["test_id"], rel(r["filename"]), r["line_number"])):
    print(f"  {r['test_id']} {rel(r['filename'])}:{r['line_number']}")
