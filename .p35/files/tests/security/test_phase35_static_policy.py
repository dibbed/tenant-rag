"""Phase 3.5 regression tests: Bandit findings are fixed, not hidden.

- Every '# nosec' in ragbot/ names its Bandit test and is in the reviewed list
  (no blanket '# nosec').
- The Bandit configuration skips no MEDIUM or HIGH test.

docs/security/PHASE3_5_SECURITY_HARDENING.md lists each suppression with its
reason.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10: tomli is installed with pytest
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]
NOSEC = re.compile(r"#\s*nosec\b(?P<rest>.*)$", re.IGNORECASE)
TEST_ID = re.compile(r"\bB\d{3}\b")
REVIEWED_SUPPRESSIONS = {
    ("ragbot/services/document_service.py", "B104"): (
        "a list of local host names that only produces a warning; not a bind address"
    ),
}


def test_every_nosec_names_a_reviewed_bandit_test() -> None:
    found: set[tuple[str, str]] = set()
    blanket: list[str] = []
    for path in sorted((ROOT / "ragbot").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = NOSEC.search(line)
            if match is None:
                continue
            tests = TEST_ID.findall(match.group("rest"))
            if not tests:
                blanket.append(f"{relative}:{number}")
            found.update((relative, test) for test in tests)
    assert blanket == []
    assert found == set(REVIEWED_SUPPRESSIONS)


def test_the_bandit_configuration_skips_no_medium_or_high_test() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["bandit"]
    assert set(config.get("skips", [])) <= {"B101"}
    assert config.get("exclude_dirs") == ["tests"]
