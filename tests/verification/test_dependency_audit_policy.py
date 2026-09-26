"""Dependency Vulnerability Check policy (REQ-MTS-CI-004), tested without network access."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

TODAY = dt.date(2026, 9, 26)
HIGH_ID = "GHSA-aaaa-bbbb-cccc"
MODERATE_ID = "GHSA-dddd-eeee-ffff"
GHSA_HIGH = {"id": HIGH_ID, "summary": "Demo high advisory", "database_specific": {"severity": "HIGH"}}
GHSA_MODERATE = {"id": MODERATE_ID, "summary": "Demo moderate advisory", "database_specific": {"severity": "MODERATE"}}


@pytest.fixture(scope="module")
def audit_module(verification_script):
    return verification_script("dependency_audit")


def _pip_audit(*dependencies: dict[str, Any]) -> dict[str, Any]:
    return {"dependencies": list(dependencies), "fixes": []}


def _dep(name: str, version: str, *vulns: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "version": version, "vulns": list(vulns)}


def _vuln(identifier: str, *aliases: str, fix: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"id": identifier, "aliases": list(aliases), "fix_versions": list(fix)}


def _exception(**overrides: str) -> dict[str, str]:
    entry = {
        "id": HIGH_ID,
        "package": "demo",
        "version": "1.0.0",
        "justification": "The vulnerable function is not used by TenantRAG.",
        "mitigation": "The feature that calls it is switched off in every deployment.",
        "owner": "@security-owner",
        "review_by": "2026-12-01",
    }
    entry.update(overrides)
    return entry


def _run(module: Any, data: Any, records: dict[str, Any], exceptions: tuple[Any, ...] = (), **options: Any):
    def fetch(identifier: str) -> dict[str, Any]:
        return records.get(identifier, {"_missing": True})

    return module.audit(data, fetch=fetch, exceptions=list(exceptions), today=TODAY, **options)


@pytest.mark.parametrize(
    ("vector", "score"),
    [
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H", 7.5),
        ("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 7.8),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
        ("CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N", 3.1),
    ],
)
def test_cvss_v3_base_score(audit_module, vector, score):
    assert audit_module.cvss3_base_score(vector) == score


def test_a_high_advisory_blocks_and_duplicate_findings_are_merged(audit_module):
    data = _pip_audit(
        _dep("demo", "1.0.0", _vuln("PYSEC-2026-1", HIGH_ID, fix=("1.1.0",)), _vuln(HIGH_ID, "PYSEC-2026-1"))
    )
    report = _run(audit_module, data, {HIGH_ID: GHSA_HIGH})
    assert report["status"] == "fail"
    assert len(report["blocking"]) == 1
    advisory = report["blocking"][0]
    assert (advisory["id"], advisory["severity"], advisory["fix_versions"]) == (HIGH_ID, "HIGH", ["1.1.0"])
    assert advisory["summary"] == "Demo high advisory"


def test_moderate_advisories_are_reported_without_blocking(audit_module):
    report = _run(audit_module, _pip_audit(_dep("demo", "1.0.0", _vuln(MODERATE_ID))), {MODERATE_ID: GHSA_MODERATE})
    assert report["status"] == "pass"
    assert [advisory["id"] for advisory in report["non_blocking"]] == [MODERATE_ID]


def test_the_threshold_can_be_lowered(audit_module):
    data = _pip_audit(_dep("demo", "1.0.0", _vuln(MODERATE_ID)))
    assert _run(audit_module, data, {MODERATE_ID: GHSA_MODERATE}, fail_on="moderate")["status"] == "fail"


def test_a_cvss_vector_is_used_without_a_github_severity(audit_module):
    record = {
        "id": "PYSEC-2026-9",
        "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
    }
    report = _run(audit_module, _pip_audit(_dep("demo", "1.0.0", _vuln("PYSEC-2026-9"))), {"PYSEC-2026-9": record})
    assert report["blocking"][0]["severity"] == "CRITICAL"


def test_an_unknown_severity_blocks(audit_module):
    data = _pip_audit(_dep("demo", "1.0.0", _vuln("PYSEC-2026-10")))
    report = _run(audit_module, data, {"PYSEC-2026-10": {"id": "PYSEC-2026-10"}})
    assert report["status"] == "fail"
    assert report["blocking"][0]["severity"] == "UNKNOWN"


def test_a_failed_lookup_is_an_error(audit_module):
    data = _pip_audit(_dep("demo", "1.0.0", _vuln(HIGH_ID)))
    assert _run(audit_module, data, {HIGH_ID: {"_error": "HTTP 503"}})["status"] == "error"


def test_a_valid_exception_accepts_the_advisory_and_is_listed(audit_module):
    data = _pip_audit(_dep("demo", "1.0.0", _vuln("PYSEC-2026-1", HIGH_ID)))
    report = _run(audit_module, data, {HIGH_ID: GHSA_HIGH}, exceptions=(_exception(),))
    assert report["status"] == "pass"
    assert report["blocking"] == []
    assert report["accepted"][0]["exception"]["owner"] == "@security-owner"


def test_an_exception_does_not_cover_another_version(audit_module):
    data = _pip_audit(_dep("demo", "1.0.1", _vuln(HIGH_ID)))
    report = _run(audit_module, data, {HIGH_ID: GHSA_HIGH}, exceptions=(_exception(),))
    assert report["status"] == "fail"
    assert report["exceptions"]["unused"][0]["id"] == HIGH_ID


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"review_by": "2026-09-01"}, "expired"),
        ({"review_by": "2028-01-01"}, "days away"),
        ({"review_by": "soon"}, "not a date"),
        ({"owner": "TBD"}, "'owner'"),
        ({"mitigation": ""}, "'mitigation'"),
        ({"id": "*"}, "not an advisory id"),
        ({"version": ">=1.0"}, "exact installed version"),
    ],
)
def test_invalid_exceptions_are_rejected_and_fail_the_check(audit_module, overrides, problem):
    data = _pip_audit(_dep("demo", "1.0.0", _vuln(HIGH_ID)))
    report = _run(audit_module, data, {HIGH_ID: GHSA_HIGH}, exceptions=(_exception(**overrides),))
    assert report["status"] == "fail"
    assert report["exceptions"]["invalid"]
    assert any(problem in text for text in report["exceptions"]["invalid"][0]["problems"])


def test_an_unaudited_dependency_blocks_but_the_project_itself_does_not(audit_module):
    project = {"name": "tenant-rag", "skip_reason": "distribution marked as editable"}
    private = {"name": "private-lib", "skip_reason": "Dependency not found on PyPI"}
    report = _run(audit_module, {"dependencies": [project, private], "fixes": []}, {})
    assert report["status"] == "fail"
    assert any("private-lib" in problem for problem in report["problems"])
    assert _run(audit_module, {"dependencies": [project], "fixes": []}, {})["status"] == "pass"


def test_unreadable_pip_audit_output_is_an_error(audit_module):
    assert _run(audit_module, {"unexpected": True}, {})["status"] == "error"


def test_the_checked_in_exceptions_file_is_valid(audit_module, repo_root):
    entries, problems = audit_module.load_exceptions(repo_root / audit_module.DEFAULT_EXCEPTIONS)
    assert problems == []
    today = dt.datetime.now(dt.timezone.utc).date()
    for entry in entries:
        assert audit_module.validate_exception(entry, today) == [], entry
