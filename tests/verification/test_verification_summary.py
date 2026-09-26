"""Verification Summary (AC-MTS-CI-001.3): every check with its outcome; a failed Blocking Check fails the gate."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

VERSIONS = ("3.10", "3.11", "3.12")
MANIFEST = {
    "path": "tests/security/suite_manifest.json",
    "paths": ["tests/security"],
    "expected": 322,
    "missing": [],
    "unexpected": [],
    "base_available": True,
    "base_ref": "abc123",
    "removed_vs_base": [],
    "added_vs_base": [],
}


@pytest.fixture(scope="module")
def summary(verification_script):
    return verification_script("summary")


@pytest.fixture
def reports(tmp_path, monkeypatch) -> Path:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    directory = tmp_path / "reports"
    directory.mkdir()
    for version in VERSIONS:
        _write(directory, f"tests-py{version}.json", _tests(version))
        _write(directory, f"security-py{version}.json", _security(version))
    for tool in ("ruff", "mypy", "bandit"):
        _write(
            directory,
            f"static-{tool}.json",
            {"check": f"static-{tool}", "mode": "report-only", "status": "findings", "summary": f"12 {tool} findings"},
        )
    _write(directory, "dependency-audit.json", _audit())
    _write(
        directory,
        "container.json",
        {
            "check": "container",
            "mode": "blocking",
            "status": "pass",
            "summary": "ready after 18 s; runtime UID 10001",
            "steps": [{"step": "user", "status": "pass", "detail": "process 1 runs as UID 10001"}],
            "details": {"uid": 10001, "runtime_user": "appuser"},
        },
    )
    return directory


def _write(directory: Path, name: str, report: dict[str, Any]) -> None:
    (directory / name).write_text(json.dumps(report), encoding="utf-8")


def _tests(version: str) -> dict[str, Any]:
    return {
        "check": "tests",
        "mode": "blocking",
        "status": "pass",
        "python": f"{version}.1",
        "summary": "935 passed, 0 failed, 0 errors, 1 skipped",
        "skipped_tests": [{"nodeid": "tests/integration/test_demo.py::test_openai", "reason": "Requires OpenAI API key"}],
    }


def _security(version: str, **overrides: Any) -> dict[str, Any]:
    report = {
        "check": "security-suite",
        "mode": "blocking",
        "status": "pass",
        "python": f"{version}.1",
        "summary": "322 passed, 0 failed, 0 errors, 0 skipped",
        "manifest": dict(MANIFEST),
        "failed_tests": [],
        "skipped_tests": [],
    }
    report.update(overrides)
    return report


def _audit(**overrides: Any) -> dict[str, Any]:
    report = {
        "check": "dependency-audit",
        "mode": "blocking",
        "status": "pass",
        "python": "3.11.9",
        "tool": "pip-audit 2.10.1 (OSV)",
        "fail_on": "high",
        "summary": "229 packages audited: 0 blocking, 0 accepted, 8 non-blocking advisories",
        "blocking": [],
        "accepted": [],
        "non_blocking": [],
        "exceptions": {"invalid": [], "unused": []},
    }
    report.update(overrides)
    return report


def _run(summary: Any, directory: Path, *extra: str) -> tuple[int, str]:
    output = directory.parent / "summary.md"
    code = summary.main(
        ["--reports", str(directory), "--python-versions", ",".join(VERSIONS), "--output", str(output), *extra]
    )
    return code, output.read_text(encoding="utf-8")


def test_every_check_is_listed_and_the_gate_passes(summary, reports):
    code, markdown = _run(summary, reports)
    assert code == 0
    assert "**Result: PASSED.**" in markdown
    for title in (
        "Tests (Python 3.10)",
        "Tests (Python 3.12)",
        "Security Regression Suite (Python 3.11)",
        "Style check (Ruff)",
        "Type check (MyPy)",
        "Insecure-pattern check (Bandit)",
        "Dependency Vulnerability Check",
        "Container Build Check",
    ):
        assert f"| {title} |" in markdown
    assert "| Report-only | Findings | 12 ruff findings |" in markdown
    assert "Accepted exceptions: none." in markdown
    assert "Runtime user: UID 10001 (USER appuser)." in markdown


def test_a_failed_security_test_fails_the_gate_and_is_named(summary, reports):
    failed = {
        "nodeid": "tests/security/test_phase2_authorization_boundaries.py::test_cross_tenant_access_is_denied",
        "message": "assert 200 == 403",
    }
    report = _security(
        "3.11",
        status="fail",
        summary="321 passed, 1 failed, 0 errors, 0 skipped",
        problems=["1 test(s) failed or had an error"],
        failed_tests=[failed],
    )
    _write(reports, "security-py3.11.json", report)
    code, markdown = _run(summary, reports)
    assert code == 1
    assert "**Result: FAILED.**" in markdown
    assert "test_cross_tenant_access_is_denied (Python 3.11): assert 200 == 403" in markdown


def test_a_missing_blocking_report_fails_the_gate(summary, reports, monkeypatch):
    (reports / "container.json").unlink()
    monkeypatch.setenv("NEEDS_JSON", json.dumps({"container": {"result": "failure"}}))
    code, markdown = _run(summary, reports, "--needs-env", "NEEDS_JSON")
    assert code == 1
    assert "| Container Build Check | Blocking | No report | no report (job result: failure) |" in markdown


def test_local_runs_can_leave_out_checks(summary, reports):
    for path in reports.iterdir():
        if path.name != "tests-py3.11.json":
            path.unlink()
    code, markdown = _run(summary, reports, "--allow-missing")
    assert code == 0
    assert "Container Build Check" not in markdown


def test_security_tests_removed_by_the_change_are_listed(summary, reports):
    manifest = dict(MANIFEST, removed_vs_base=["tests/security/test_old.py::test_gone"])
    for version in VERSIONS:
        _write(reports, f"security-py{version}.json", _security(version, manifest=manifest))
    code, markdown = _run(summary, reports)
    assert code == 0
    assert "Security tests removed from the manifest by this change (1)" in markdown
    assert "tests/security/test_old.py::test_gone" in markdown


def test_accepted_exceptions_are_listed(summary, reports):
    accepted = {
        "package": "demo",
        "version": "1.0.0",
        "id": "GHSA-aaaa-bbbb-cccc",
        "severity": "HIGH",
        "fix_versions": [],
        "summary": "",
        "exception": {
            "owner": "@owner",
            "review_by": "2026-12-01",
            "justification": "not reachable",
            "mitigation": "switched off",
        },
    }
    _write(reports, "dependency-audit.json", _audit(accepted=[accepted]))
    code, markdown = _run(summary, reports)
    assert code == 0
    assert "| GHSA-aaaa-bbbb-cccc | demo | 1.0.0 | HIGH | @owner | 2026-12-01 | not reachable | switched off |" in markdown


def test_a_blocking_advisory_fails_the_gate(summary, reports):
    advisory = {
        "package": "demo",
        "version": "1.0.0",
        "id": "GHSA-aaaa-bbbb-cccc",
        "severity": "CRITICAL",
        "fix_versions": ["1.0.1"],
        "summary": "Remote code execution",
    }
    _write(reports, "dependency-audit.json", _audit(status="fail", blocking=[advisory], problems=["1 advisory"]))
    code, markdown = _run(summary, reports)
    assert code == 1
    assert "| demo | 1.0.0 | GHSA-aaaa-bbbb-cccc | CRITICAL | 1.0.1 | Remote code execution |" in markdown
