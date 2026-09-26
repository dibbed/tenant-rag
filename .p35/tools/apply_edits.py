#!/usr/bin/env python3
"""Temporary Phase 3.5 workspace tool: apply exact text edits to a checkout.

Edit file format:

    @@@@FILE path/to/file
    @@@@OLD [count=N]
    ...exact old lines...
    @@@@NEW
    ...new lines...
    @@@@END

    @@@@DELETE path/to/file

Each OLD text must occur exactly N times (default 1) in the current content.
If any edit does not match, nothing is written and the exit status is 1.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path


def parse(text: str, source: str) -> list[tuple]:
    ops: list[tuple] = []
    lines = text.split("\n")
    i = 0
    current = None
    while i < len(lines):
        line = lines[i]
        if line.startswith("@@@@FILE "):
            current = line[len("@@@@FILE "):].strip()
            i += 1
        elif line.startswith("@@@@OLD"):
            rest = line[len("@@@@OLD"):].strip()
            count = int(rest[len("count="):]) if rest.startswith("count=") else 1
            i += 1
            old: list[str] = []
            while not lines[i].startswith("@@@@NEW"):
                old.append(lines[i])
                i += 1
            i += 1
            new: list[str] = []
            while not lines[i].startswith("@@@@END"):
                new.append(lines[i])
                i += 1
            i += 1
            if current is None:
                raise SystemExit(f"{source}: OLD block before FILE")
            ops.append(("edit", current, "\n".join(old) + "\n", ("\n".join(new) + "\n") if new else "", count))
        elif line.startswith("@@@@DELETE "):
            ops.append(("delete", line[len("@@@@DELETE "):].strip(), None, None, None))
            i += 1
        elif line.strip() == "" or line.startswith("#"):
            i += 1
        else:
            raise SystemExit(f"{source}: unexpected line {i + 1}: {line!r}")
    return ops


def diagnose(text: str, old: str) -> str:
    flines = text.split("\n")
    olines = old.rstrip("\n").split("\n")
    best_k, best_j = 0, -1
    for j in range(len(flines)):
        k = 0
        while k < len(olines) and j + k < len(flines) and flines[j + k] == olines[k]:
            k += 1
        if k > best_k:
            best_k, best_j = k, j
    if best_j < 0:
        close = difflib.get_close_matches(olines[0], flines, n=3, cutoff=0.5)
        return f"  no file line equals the first OLD line {olines[0]!r}; close lines: {close!r}"
    msg = f"  best match at file line {best_j + 1}: {best_k}/{len(olines)} lines equal"
    if best_k < len(olines):
        got = flines[best_j + best_k] if best_j + best_k < len(flines) else "<EOF>"
        msg += f"\n  first difference at OLD line {best_k + 1}: expected {olines[best_k]!r}"
        msg += f"\n  file line {best_j + best_k + 1}: {got!r}"
    return msg


def main(argv: list[str]) -> int:
    repo = Path(argv[0])
    contents: dict[str, str] = {}
    deletes: list[str] = []
    errors: list[str] = []
    applied = 0
    for edit_file in argv[1:]:
        for kind, path, old, new, count in parse(Path(edit_file).read_text(encoding="utf-8"), edit_file):
            target = repo / path
            if kind == "delete":
                if not target.exists():
                    errors.append(f"{edit_file}: DELETE {path}: file does not exist")
                deletes.append(path)
                continue
            if path not in contents:
                if not target.exists():
                    errors.append(f"{edit_file}: {path}: file does not exist")
                    continue
                contents[path] = target.read_text(encoding="utf-8")
            found = contents[path].count(old)
            if found != count:
                errors.append(
                    f"{edit_file}: {path}: OLD found {found} times, expected {count}. OLD starts with "
                    f"{old[:160]!r}\n{diagnose(contents[path], old)}"
                )
                continue
            contents[path] = contents[path].replace(old, new)
            applied += 1
    if errors:
        print("\n".join(errors))
        print(f"NOT APPLIED: {len(errors)} error(s)")
        return 1
    for path, text in contents.items():
        (repo / path).write_text(text, encoding="utf-8")
    for path in deletes:
        (repo / path).unlink()
    print(f"applied {applied} edit(s) to {len(contents)} file(s); deleted {len(deletes)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
