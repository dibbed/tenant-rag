"""Temporary Phase 3.5 workspace tool: print the content of downloaded verification reports."""

import json
import sys
from pathlib import Path


def short(value, limit):
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return text if len(text) <= limit else text[:limit] + f"...(+{len(text) - limit})"


root = Path(sys.argv[1])
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 500
for path in sorted(root.rglob("*.json")):
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"== {path}: unreadable: {exc}")
        continue
    if not isinstance(report, dict):
        continue
    print(f"== {path.relative_to(root)}")
    for key in sorted(report):
        value = report[key]
        if isinstance(value, dict) and key == "details":
            for sub in sorted(value):
                print(f"   details.{sub}: {short(value[sub], limit)}")
        elif isinstance(value, list):
            print(f"   {key}: list[{len(value)}] {short(value, limit)}")
        else:
            print(f"   {key}: {short(value, limit)}")
