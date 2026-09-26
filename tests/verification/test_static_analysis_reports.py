"""Static Analysis Checks (REQ-MTS-CI-003): findings are counted and the exit status of the tool is kept."""

from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

RUFF = json.dumps(
    [
        {"code": "F401", "filename": "/repo/a.py"},
        {"code": "F401", "filename": "/repo/b.py"},
        {"code": "E711", "filename": "/repo/a.py"},
    ]
)
MYPY = (
    "ragbot/a.py:3: error: Missing return statement  [return]\n"
    'ragbot/b.py:9: error: Name "x" is not defined  [name-defined]\n'
    "ragbot/b.py:9: note: a note\n"
    "Found 2 errors in 2 files (checked 5 source files)\n"
)
BANDIT = json.dumps(
    {
        "results": [
            {
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "test_id": "B324",
                "test_name": "hashlib",
                "filename": "ragbot/a.py",
                "line_number": 4,
                "issue_text": "Use of weak MD5 hash for security.",
            },
            {
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "test_id": "B110",
                "test_name": "try_except_pass",
                "filename": "ragbot/b.py",
                "line_number": 7,
                "issue_text": "Try, Except, Pass detected.",
            },
        ],
        "errors": [],
    }
)


@pytest.fixture(scope="module")
def static(verification_script):
    return verification_script("static_analysis")


def _runner(stdout: str, returncode: int):
    def run(command: list[str], **_options: Any) -> subprocess.CompletedProcess[str]:
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, "tool 1.0\n", "")
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    return run


def test_ruff_findings_are_counted_by_code_and_keep_exit_status_1(static):
    report = static.run_check("ruff", "report-only", runner=_runner(RUFF, 1))
    assert (report["status"], report["findings"]) == ("findings", 3)
    assert report["details"]["by_code"] == {"F401": 2, "E711": 1}
    assert static.exit_code(report) == 1


def test_mypy_errors_and_the_summary_line_are_read(static):
    report = static.run_check("mypy", "report-only", runner=_runner(MYPY, 1))
    assert report["findings"] == 2
    assert report["details"]["summary_line"] == "Found 2 errors in 2 files (checked 5 source files)"
    assert report["details"]["by_code"] == {"return": 1, "name-defined": 1}


def test_bandit_findings_are_counted_by_severity(static):
    report = static.run_check("bandit", "report-only", runner=_runner(BANDIT, 1))
    assert report["details"]["by_severity"] == {"HIGH": 1, "MEDIUM": 0, "LOW": 1}
    assert report["annotations"][0]["file"] == "ragbot/a.py"
    assert report["summary"] == "2 findings: 1 high, 0 medium, 1 low severity"


def test_blocking_mode_fails_on_findings(static):
    report = static.run_check("ruff", "blocking", runner=_runner(RUFF, 1))
    assert report["status"] == "fail"
    assert static.exit_code(report) == 1


def test_no_finding_passes(static):
    report = static.run_check("ruff", "report-only", runner=_runner("[]", 0))
    assert report["status"] == "pass"
    assert static.exit_code(report) == 0


@pytest.mark.parametrize(
    ("tool", "stdout", "returncode"),
    [("ruff", "not json", 2), ("mypy", "error: INTERNAL ERROR\n", 2), ("bandit", "", 2)],
)
def test_a_tool_that_cannot_run_is_an_error(static, tool, stdout, returncode):
    report = static.run_check(tool, "report-only", runner=_runner(stdout, returncode))
    assert report["status"] == "error"
    assert static.exit_code(report) == 2


def test_the_tool_pins_come_from_the_dev_extra(static, repo_root, capsys):
    assert static.print_pins(["ruff", "bandit", "mypy"], repo_root) == 0
    lines = capsys.readouterr().out.split()
    assert [line.split("==")[0] for line in lines] == ["ruff", "bandit", "mypy"]
