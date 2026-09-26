"""The Verification Pipeline workflow has the triggers, checks and settings of REQ-MTS-CI-001 to 005."""

from __future__ import annotations

import re
import sys
from typing import Any

import pytest
import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:  # Python 3.10: tomli is installed with pytest
    import tomli as tomllib

PINNED_ACTION = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
BLOCKING_JOBS = ("tests", "security-suite", "dependency-audit", "container", "summary")


@pytest.fixture(scope="module")
def workflow(repo_root) -> dict[str, Any]:
    text = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


@pytest.fixture(scope="module")
def supported_versions(repo_root) -> list[str]:
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    versions = sorted(
        classifier.rsplit("::", 1)[1].strip()
        for classifier in data["project"]["classifiers"]
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", classifier)
    )
    assert versions, "pyproject.toml lists no supported Python version"
    return versions


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    # PyYAML reads the key "on" as the boolean True (YAML 1.1).
    return workflow.get("on", workflow.get(True))


def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in job.get("steps", []))


def test_the_pipeline_runs_for_changes_proposed_to_and_landing_on_main(workflow):
    triggers = _triggers(workflow)
    assert "main" in triggers["pull_request"]["branches"]
    assert "main" in triggers["push"]["branches"]


def test_tests_and_security_suite_run_on_every_supported_python(workflow, supported_versions):
    for name in ("tests", "security-suite"):
        matrix = workflow["jobs"][name]["strategy"]["matrix"]
        assert sorted(matrix["python-version"]) == supported_versions, name
    assert "--python-versions " + ",".join(supported_versions) in _run_text(workflow["jobs"]["summary"])


def test_every_check_has_a_stable_name(workflow):
    jobs = workflow["jobs"]
    assert jobs["tests"]["name"] == "Tests (Python ${{ matrix.python-version }})"
    assert jobs["security-suite"]["name"] == "Security Regression Suite (Python ${{ matrix.python-version }})"
    assert jobs["static-analysis"]["name"] == "Static Analysis (${{ matrix.tool }}, ${{ matrix.mode }})"
    assert jobs["dependency-audit"]["name"] == "Dependency Vulnerability Check"
    assert jobs["container"]["name"] == "Container Build Check"
    assert jobs["summary"]["name"] == "Verification Summary"


def test_blocking_checks_never_continue_on_error(workflow):
    for name in BLOCKING_JOBS:
        job = workflow["jobs"][name]
        assert "continue-on-error" not in job, name
        for step in job["steps"]:
            assert not step.get("continue-on-error", False), (name, step.get("name"))


def test_static_checks_run_every_tool_and_keep_their_exit_status(workflow):
    job = workflow["jobs"]["static-analysis"]
    include = job["strategy"]["matrix"]["include"]
    assert {entry["tool"] for entry in include} == {"ruff", "mypy", "bandit"}
    assert {entry["mode"] for entry in include} <= {"report-only", "blocking"}
    assert job["continue-on-error"] == "${{ matrix.mode == 'report-only' }}"
    assert "--mode ${{ matrix.mode }}" in _run_text(job)


def test_the_summary_needs_every_check_and_always_runs(workflow):
    jobs = workflow["jobs"]
    summary = jobs["summary"]
    assert set(summary["needs"]) == set(jobs) - {"summary"}
    assert "always()" in summary["if"]


def test_least_privilege_and_pinned_actions(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for name, job in workflow["jobs"].items():
        for level in (job.get("permissions") or {}).values():
            assert level in ("read", "none"), name
        for step in job["steps"]:
            uses = step.get("uses")
            if not uses:
                continue
            assert PINNED_ACTION.match(uses), f"{name}: {uses} is not pinned to a commit"
            if uses.startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False, name


def test_the_security_suite_has_redis(workflow):
    job = workflow["jobs"]["security-suite"]
    assert "redis" in job["services"]
    assert any("TEST_REDIS_URL" in (step.get("env") or {}) for step in job["steps"])


def test_the_container_check_always_removes_its_containers(workflow):
    steps = workflow["jobs"]["container"]["steps"]
    cleanup = [step for step in steps if "label=tenant-rag-verification" in str(step.get("run", ""))]
    assert cleanup, "no cleanup step"
    assert cleanup[0].get("if") == "always()"
