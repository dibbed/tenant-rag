"""Security Regression Suite gate (REQ-MTS-CI-002): independent collection, no skip, manifest check."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

ALPHA = "tests/security/test_demo.py::test_alpha"
BETA = "tests/security/test_demo.py::test_beta"
MANIFEST = {"paths": ["tests/security"], "tests": [ALPHA, BETA]}
SAMPLE_WITH_SKIP = (
    "import pytest\n\n\n"
    "def test_ok():\n    assert True\n\n\n"
    "@pytest.mark.skip(reason='not ready')\n"
    "def test_skipped():\n    pass\n"
)


@pytest.fixture(scope="module")
def run_suite(verification_script):
    return verification_script("run_suite")


def _raw(outcomes: dict[str, str], **extra: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "python": "3.11.9",
        "exit_status": 0,
        "collected": list(outcomes),
        "deselected": [],
        "outcomes": outcomes,
        "skip_reasons": {},
        "failures": {},
        "collection_problems": [],
    }
    raw.update(extra)
    return raw


def _passing() -> dict[str, str]:
    return {ALPHA: "passed", BETA: "passed"}


def test_a_clean_run_passes(run_suite):
    report = run_suite.evaluate_security(_raw(_passing()), 0, MANIFEST, "manifest.json")
    assert report["status"] == "pass"
    assert report["counts"]["passed"] == 2
    assert report["problems"] == []


def test_a_skipped_security_test_fails_the_suite_and_is_named(run_suite):
    raw = _raw(_passing() | {BETA: "skipped"}, skip_reasons={BETA: "TEST_REDIS_URL is not set"})
    report = run_suite.evaluate_security(raw, 0, MANIFEST, "manifest.json")
    assert report["status"] == "fail"
    assert report["skipped_tests"] == [
        {"nodeid": BETA, "outcome": "skipped", "reason": "TEST_REDIS_URL is not set"}
    ]
    assert any("allows no skipped test" in problem for problem in report["problems"])


def test_an_xfail_security_test_also_fails_the_suite(run_suite):
    report = run_suite.evaluate_security(_raw(_passing() | {ALPHA: "xfailed"}), 0, MANIFEST, "manifest.json")
    assert report["status"] == "fail"
    assert [item["nodeid"] for item in report["skipped_tests"]] == [ALPHA]


def test_failed_security_tests_are_named_with_their_message(run_suite):
    raw = _raw(
        _passing() | {ALPHA: "failed"},
        exit_status=1,
        failures={ALPHA: "AssertionError: tenant B read a document of tenant A"},
    )
    report = run_suite.evaluate_security(raw, 1, MANIFEST, "manifest.json")
    assert report["status"] == "fail"
    assert report["failed_tests"][0]["nodeid"] == ALPHA
    assert "tenant B read a document of tenant A" in report["failed_tests"][0]["message"]


def test_a_removed_security_test_is_reported_as_missing(run_suite):
    report = run_suite.evaluate_security(_raw({ALPHA: "passed"}), 0, MANIFEST, "manifest.json")
    assert report["status"] == "fail"
    assert report["manifest"]["missing"] == [BETA]


def test_a_new_security_test_must_be_added_to_the_manifest(run_suite):
    gamma = "tests/security/test_demo.py::test_gamma"
    report = run_suite.evaluate_security(_raw(_passing() | {gamma: "passed"}), 0, MANIFEST, "manifest.json")
    assert report["status"] == "fail"
    assert report["manifest"]["unexpected"] == [gamma]
    assert any("--update-manifest" in problem for problem in report["problems"])


def test_a_removal_recorded_in_the_manifest_is_listed_against_the_base(run_suite):
    removed = "tests/security/test_demo.py::test_removed"
    base = {"paths": MANIFEST["paths"], "tests": [*MANIFEST["tests"], removed]}
    report = run_suite.evaluate_security(
        _raw(_passing()), 0, MANIFEST, "manifest.json", base_manifest=base, base_ref="abc123"
    )
    assert report["status"] == "pass"
    assert report["manifest"]["removed_vs_base"] == [removed]
    assert report["manifest"]["added_vs_base"] == []


def test_a_file_skipped_during_collection_fails_the_suite(run_suite):
    problem = {"nodeid": "tests/security/test_other.py", "outcome": "skipped", "detail": "could not import 'redis'"}
    report = run_suite.evaluate_security(
        _raw(_passing(), collection_problems=[problem]), 0, MANIFEST, "manifest.json"
    )
    assert report["status"] == "fail"


def test_the_full_suite_allows_skips_but_not_failures(run_suite):
    first = "tests/unit/test_demo.py::test_a"
    second = "tests/unit/test_demo.py::test_b"
    assert run_suite.evaluate_full(_raw({first: "passed", second: "skipped"}), 0)["status"] == "pass"
    failed = run_suite.evaluate_full(_raw({first: "failed"}, exit_status=1), 1)
    assert failed["status"] == "fail"
    assert failed["failed_tests"][0]["nodeid"] == first


def test_a_missing_pytest_report_is_an_error(run_suite):
    assert run_suite.evaluate_full(None, 4)["status"] == "error"
    assert run_suite.evaluate_security(None, 4, MANIFEST, "manifest.json")["status"] == "error"


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps([]),
        json.dumps({"paths": [], "tests": []}),
        json.dumps({"paths": ["tests"], "tests": ["no-separator"]}),
        json.dumps({"paths": ["tests"], "tests": ["a.py::t", "a.py::t"]}),
    ],
)
def test_invalid_manifests_are_rejected(run_suite, tmp_path, content):
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(run_suite.ManifestError):
        run_suite.load_manifest(path)


def test_the_checked_in_manifest_is_sorted_and_inside_its_paths(run_suite, repo_root):
    manifest = run_suite.load_manifest(repo_root / run_suite.DEFAULT_MANIFEST)
    assert manifest["tests"], "the manifest lists no security test"
    assert manifest["tests"] == sorted(manifest["tests"])
    for path in manifest["paths"]:
        assert (repo_root / path).exists(), path
    for nodeid in manifest["tests"]:
        file_part = nodeid.split("::", 1)[0]
        assert any(
            file_part == path or file_part.startswith(path.rstrip("/") + "/") for path in manifest["paths"]
        ), nodeid


@pytest.mark.usefixtures("clean_coverage_env")
def test_the_security_suite_collects_on_its_own_and_matches_the_manifest(run_suite):
    assert run_suite.main(["security", "--check-manifest"]) == 0


def _project(root: Path, body: str, tests: list[str]) -> Path:
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_sample.py").write_text(body, encoding="utf-8")
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"paths": ["tests"], "tests": tests}), encoding="utf-8")
    return manifest


@pytest.mark.usefixtures("clean_coverage_env")
def test_the_runner_fails_on_a_real_skipped_test(run_suite, tmp_path):
    manifest = _project(
        tmp_path, SAMPLE_WITH_SKIP, ["tests/test_sample.py::test_ok", "tests/test_sample.py::test_skipped"]
    )
    report_path = tmp_path / "report.json"
    code = run_suite.main(
        ["security", "--root", str(tmp_path), "--manifest", str(manifest), "--report", str(report_path)]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 1
    assert report["counts"]["passed"] == 1
    assert [item["nodeid"] for item in report["skipped_tests"]] == ["tests/test_sample.py::test_skipped"]
    assert "not ready" in report["skipped_tests"][0]["reason"]


@pytest.mark.usefixtures("clean_coverage_env")
def test_the_runner_detects_a_removed_test(run_suite, tmp_path):
    manifest = _project(
        tmp_path, "def test_ok():\n    assert True\n", ["tests/test_sample.py::test_ok", "tests/test_sample.py::test_removed"]
    )
    report_path = tmp_path / "report.json"
    code = run_suite.main(
        ["security", "--root", str(tmp_path), "--manifest", str(manifest), "--report", str(report_path)]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 1
    assert report["manifest"]["missing"] == ["tests/test_sample.py::test_removed"]


@pytest.mark.usefixtures("clean_coverage_env")
def test_update_manifest_writes_the_sorted_node_ids(run_suite, tmp_path):
    manifest = _project(tmp_path, "def test_b():\n    pass\n\n\ndef test_a():\n    pass\n", [])
    code = run_suite.main(["security", "--root", str(tmp_path), "--manifest", str(manifest), "--update-manifest"])
    assert code == 0
    written = json.loads(manifest.read_text(encoding="utf-8"))
    assert written["tests"] == ["tests/test_sample.py::test_a", "tests/test_sample.py::test_b"]
