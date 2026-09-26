#!/usr/bin/env python3
"""Run the full test suite or the Security Regression Suite and apply its gate policy.

Full test suite (Blocking Check "Tests"):

    python scripts/verification/run_suite.py full [--report PATH] [-- PYTEST_ARGS...]

    Fails when a test fails or has an error, when a test file cannot be
    collected, or when no test runs. Skipped tests are allowed; the report
    lists each one with its reason.

Security Regression Suite (Blocking Check "Security Regression Suite"):

    python scripts/verification/run_suite.py security [--report PATH]
        [--base-manifest FILE] [--base-ref REF] [-- PYTEST_ARGS...]

    Runs the paths listed in tests/security/suite_manifest.json. Fails when a
    test fails, has an error, is skipped or is marked xfail, when a test file
    cannot be collected or is skipped as a whole, and when the collected tests
    differ from the manifest: a listed test is missing (removed or renamed) or
    a new test is not listed. With --base-manifest (the manifest of the base
    commit) the report also lists the tests that the change removed from, or
    added to, the manifest.

    python scripts/verification/run_suite.py security --check-manifest
        Collect only and compare the collected tests with the manifest.

    python scripts/verification/run_suite.py security --update-manifest
        Collect the suite paths and write the sorted test list into the
        manifest. Review the diff and commit it with the test change.

Exit codes: 0 passed, 1 failed, 2 usage or infrastructure error.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = Path(__file__).resolve().parent / "pytest_plugin"
PLUGIN_MODULE = "verification_outcomes"
REPORT_ENV = "VERIFICATION_PYTEST_REPORT"
DEFAULT_MANIFEST = Path("tests/security/suite_manifest.json")
FAIL_OUTCOMES = frozenset({"failed", "error"})
SKIP_OUTCOMES = frozenset({"skipped", "xfailed"})
UPDATE_COMMAND = "python scripts/verification/run_suite.py security --update-manifest"
MAX_ANNOTATION_ITEMS = 25


class ManifestError(ValueError):
    """The manifest file is missing or not valid."""


def load_manifest(path: Path) -> dict[str, Any]:
    """Read and validate a Security Regression Suite manifest."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a JSON object")
    paths = data.get("paths")
    tests = data.get("tests")
    if not isinstance(paths, list) or not paths:
        raise ManifestError("manifest 'paths' must be a non-empty list of test paths")
    if not all(isinstance(item, str) and item.strip() for item in paths):
        raise ManifestError("manifest 'paths' must contain only non-empty strings")
    if not isinstance(tests, list):
        raise ManifestError("manifest 'tests' must be a list of pytest node ids")
    if not all(isinstance(item, str) and "::" in item for item in tests):
        raise ManifestError("manifest 'tests' must contain only pytest node ids")
    if len(set(tests)) != len(tests):
        raise ManifestError("manifest 'tests' lists a node id more than once")
    return data


def coverage_args() -> list[str]:
    """Options that switch off the coverage options of the pytest addopts."""
    return ["--no-cov"] if importlib.util.find_spec("pytest_cov") else []


def run_pytest(
    targets: list[str],
    pytest_args: list[str],
    root: Path,
    *,
    collect_only: bool = False,
) -> tuple[int, dict[str, Any] | None]:
    """Run pytest with the outcome recorder; return (exit code, recorded report)."""
    with tempfile.TemporaryDirectory(prefix="verification-") as tmp:
        report_path = Path(tmp) / "pytest-report.json"
        env = dict(os.environ)
        env[REPORT_ENV] = str(report_path)
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(PLUGIN_DIR), env.get("PYTHONPATH", "")) if part
        )
        command = [sys.executable, "-m", "pytest", "-p", PLUGIN_MODULE, *pytest_args]
        if collect_only:
            command += ["--collect-only", "-q"]
        command += targets
        print("+ " + " ".join(command), flush=True)
        returncode = subprocess.run(command, cwd=root, env=env, check=False).returncode
        raw = None
        if report_path.exists():
            raw = json.loads(report_path.read_text(encoding="utf-8"))
    return returncode, raw


def count_outcomes(raw: dict[str, Any]) -> dict[str, int]:
    """Number of collected tests and number of tests per outcome."""
    outcomes = raw.get("outcomes", {})
    counts = {"collected": len(raw.get("collected", []))}
    for name in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"):
        counts[name] = sum(1 for value in outcomes.values() if value == name)
    return counts


def summary_line(counts: dict[str, int]) -> str:
    """One line such as '935 passed, 0 failed, 0 errors, 1 skipped'."""
    parts = [
        f"{counts.get('passed', 0)} passed",
        f"{counts.get('failed', 0)} failed",
        f"{counts.get('error', 0)} errors",
        f"{counts.get('skipped', 0)} skipped",
    ]
    parts += [f"{counts[name]} {name}" for name in ("xfailed", "xpassed") if counts.get(name)]
    return ", ".join(parts)


def _new_report(check: str, title: str) -> dict[str, Any]:
    return {
        "schema": 1,
        "check": check,
        "title": title,
        "mode": "blocking",
        "python": platform.python_version(),
    }


def evaluate_full(raw: dict[str, Any] | None, returncode: int) -> dict[str, Any]:
    """Policy of the full test suite: no failed test and no collection error."""
    report = _new_report("tests", "Tests")
    if raw is None:
        problem = f"pytest did not write a report (exit code {returncode})"
        report.update(
            status="error",
            summary=problem,
            counts={},
            problems=[problem],
            failed_tests=[],
            skipped_tests=[],
            collection_problems=[],
            not_run=[],
        )
        return report
    outcomes = raw.get("outcomes", {})
    failures = raw.get("failures", {})
    reasons = raw.get("skip_reasons", {})
    collected = list(raw.get("collected", []))
    collection_problems = list(raw.get("collection_problems", []))
    counts = count_outcomes(raw)
    failed = sorted(name for name, outcome in outcomes.items() if outcome in FAIL_OUTCOMES)
    skipped = sorted(name for name, outcome in outcomes.items() if outcome in SKIP_OUTCOMES)
    collection_errors = [item for item in collection_problems if item.get("outcome") == "error"]
    not_run = [name for name in collected if name not in outcomes]
    problems = []
    if failed:
        problems.append(f"{len(failed)} test(s) failed or had an error")
    if collection_errors:
        problems.append(f"{len(collection_errors)} test file(s) could not be collected")
    if not collected:
        problems.append("no test was collected")
    if not_run:
        problems.append(f"{len(not_run)} collected test(s) did not run")
    if returncode != 0 and not problems:
        problems.append(f"pytest exited with code {returncode}")
    report.update(
        python=raw.get("python") or report["python"],
        status="fail" if problems else "pass",
        summary=summary_line(counts),
        counts=counts,
        problems=problems,
        failed_tests=[
            {"nodeid": name, "outcome": outcomes[name], "message": failures.get(name, "")}
            for name in failed
        ],
        skipped_tests=[
            {"nodeid": name, "outcome": outcomes[name], "reason": reasons.get(name, "")}
            for name in skipped
        ],
        collection_problems=collection_problems,
        not_run=not_run,
        duration_seconds=raw.get("duration_seconds"),
    )
    return report


def compare_with_manifest(collected: list[str], expected: list[str]) -> tuple[list[str], list[str]]:
    """Return (tests in the manifest but not collected, collected tests not in the manifest)."""
    return sorted(set(expected) - set(collected)), sorted(set(collected) - set(expected))


def evaluate_security(
    raw: dict[str, Any] | None,
    returncode: int,
    manifest: dict[str, Any],
    manifest_name: str,
    *,
    base_manifest: dict[str, Any] | None = None,
    base_ref: str | None = None,
    missing_paths: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Policy of the Security Regression Suite: every listed test ran and passed."""
    report = evaluate_full(raw, returncode)
    report.update(check="security-suite", title="Security Regression Suite")
    problems = list(report["problems"])
    expected = list(manifest["tests"])
    details: dict[str, Any] = {
        "path": manifest_name,
        "paths": list(manifest["paths"]),
        "expected": len(expected),
        "missing": [],
        "unexpected": [],
        "base_ref": base_ref,
        "base_available": base_manifest is not None,
        "removed_vs_base": [],
        "added_vs_base": [],
    }
    if missing_paths:
        problems.append("manifest path(s) not found: " + ", ".join(missing_paths))
    if raw is not None:
        missing, unexpected = compare_with_manifest(list(raw.get("collected", [])), expected)
        details.update(missing=missing, unexpected=unexpected)
        file_skips = [
            item for item in raw.get("collection_problems", []) if item.get("outcome") == "skipped"
        ]
        deselected = list(raw.get("deselected", []))
        if report["skipped_tests"]:
            problems.append(
                f"{len(report['skipped_tests'])} security test(s) skipped or marked xfail; "
                "the Security Regression Suite allows no skipped test"
            )
        if file_skips:
            problems.append(f"{len(file_skips)} security test file(s) skipped during collection")
        if deselected:
            problems.append(f"{len(deselected)} security test(s) deselected")
        if missing:
            problems.append(
                f"{len(missing)} test(s) in the manifest were not collected (removed or renamed)"
            )
        if unexpected:
            problems.append(
                f"{len(unexpected)} collected test(s) are not in the manifest; "
                f"run '{UPDATE_COMMAND}' and commit the manifest"
            )
    if base_manifest is not None:
        base_tests = set(base_manifest.get("tests", []))
        details["removed_vs_base"] = sorted(base_tests - set(expected))
        details["added_vs_base"] = sorted(set(expected) - base_tests)
    report["manifest"] = details
    report["problems"] = problems
    if report["status"] != "error":
        report["status"] = "fail" if problems else "pass"
    return report


def evaluate_collection(
    raw: dict[str, Any] | None,
    returncode: int,
    manifest: dict[str, Any],
    manifest_name: str,
    missing_paths: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Compare a collect-only run with the manifest."""
    report = _new_report("security-suite-manifest", "Security Regression Suite manifest")
    details: dict[str, Any] = {
        "path": manifest_name,
        "paths": list(manifest["paths"]),
        "expected": len(manifest["tests"]),
        "missing": [],
        "unexpected": [],
    }
    problems = []
    if missing_paths:
        problems.append("manifest path(s) not found: " + ", ".join(missing_paths))
    if raw is None:
        problems.append(f"pytest did not write a report (exit code {returncode})")
        report.update(
            status="error",
            summary=problems[-1],
            problems=problems,
            manifest=details,
            collection_problems=[],
        )
        return report
    collected = list(raw.get("collected", []))
    collection_problems = list(raw.get("collection_problems", []))
    missing, unexpected = compare_with_manifest(collected, manifest["tests"])
    details.update(missing=missing, unexpected=unexpected, collected=len(collected))
    if any(item.get("outcome") == "error" for item in collection_problems):
        problems.append("test file(s) could not be collected")
    if any(item.get("outcome") == "skipped" for item in collection_problems):
        problems.append("test file(s) skipped during collection")
    if missing:
        problems.append(
            f"{len(missing)} test(s) in the manifest were not collected (removed or renamed)"
        )
    if unexpected:
        problems.append(
            f"{len(unexpected)} collected test(s) are not in the manifest; run '{UPDATE_COMMAND}'"
        )
    if returncode != 0 and not problems:
        problems.append(f"pytest exited with code {returncode}")
    report.update(
        python=raw.get("python") or report["python"],
        status="fail" if problems else "pass",
        summary=f"{len(collected)} tests collected, {len(manifest['tests'])} tests in the manifest",
        problems=problems,
        collection_problems=collection_problems,
        manifest=details,
    )
    return report


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def annotate(level: str, title: str, items: list[str]) -> None:
    """Print a GitHub Actions annotation (only when running in GitHub Actions)."""
    if os.environ.get("GITHUB_ACTIONS") != "true" or not items:
        return
    shown = list(items[:MAX_ANNOTATION_ITEMS])
    if len(items) > len(shown):
        shown.append(f"... and {len(items) - len(shown)} more (see the job log and the report)")
    message = "\n".join(shown)
    print(f"::{level} title={_escape_property(title)}::{_escape_data(message)}", flush=True)


def _print_items(title: str, items: list[str]) -> None:
    if not items:
        return
    print(f"{title} ({len(items)}):")
    for item in items:
        print(f"  {item}")


def print_report(report: dict[str, Any]) -> None:
    """Print a readable summary of the report."""
    print()
    print(f"== {report['title']} (Python {report.get('python')}): {report['status'].upper()} ==")
    print(report.get("summary", ""))
    for problem in report.get("problems", []):
        print(f"- {problem}")
    _print_items(
        "Failed tests",
        [f"{item['nodeid']}: {item['message']}" for item in report.get("failed_tests", [])],
    )
    _print_items(
        "Skipped tests",
        [f"{item['nodeid']}: {item['reason']}" for item in report.get("skipped_tests", [])],
    )
    _print_items(
        "Collection problems",
        [
            f"{item['nodeid']} ({item['outcome']}): {item['detail']}"
            for item in report.get("collection_problems", [])
        ],
    )
    manifest = report.get("manifest") or {}
    _print_items("In the manifest but not collected (removed or renamed)", manifest.get("missing", []))
    _print_items("Collected but not in the manifest", manifest.get("unexpected", []))
    _print_items("Removed from the manifest by this change", manifest.get("removed_vs_base", []))
    _print_items("Added to the manifest by this change", manifest.get("added_vs_base", []))


def emit_annotations(report: dict[str, Any]) -> None:
    """Annotations for failures, skips and manifest differences."""
    title = f"{report['title']} (Python {report.get('python')})"
    annotate(
        "error",
        f"{title}: failed tests",
        [f"{item['nodeid']}: {item['message']}" for item in report.get("failed_tests", [])],
    )
    if report["check"] != "tests":
        annotate(
            "error",
            f"{title}: skipped tests",
            [f"{item['nodeid']}: {item['reason']}" for item in report.get("skipped_tests", [])],
        )
    annotate(
        "error",
        f"{title}: collection problems",
        [
            f"{item['nodeid']}: {item['detail']}"
            for item in report.get("collection_problems", [])
            if report["check"] != "tests" or item.get("outcome") == "error"
        ],
    )
    manifest = report.get("manifest") or {}
    annotate("error", f"{title}: tests missing from the collection", manifest.get("missing", []))
    annotate("error", f"{title}: tests not in the manifest", manifest.get("unexpected", []))
    annotate("warning", f"{title}: tests removed from the manifest", manifest.get("removed_vs_base", []))
    if report["status"] == "error":
        annotate("error", title, list(report.get("problems", [])))


def write_report(path: Path | None, report: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def finish(report: dict[str, Any], path: Path | None) -> int:
    print_report(report)
    emit_annotations(report)
    write_report(path, report)
    return {"pass": 0, "fail": 1}.get(report["status"], 2)


def update_manifest(
    manifest_path: Path,
    manifest: dict[str, Any],
    raw: dict[str, Any] | None,
    returncode: int,
    missing_paths: list[str],
) -> int:
    """Write the collected node ids into the manifest."""
    if missing_paths:
        print("error: manifest path(s) not found: " + ", ".join(missing_paths), file=sys.stderr)
        return 2
    if raw is None or returncode != 0:
        print(f"error: collection failed (exit code {returncode}); the manifest was not changed", file=sys.stderr)
        return 2
    problems = [
        item for item in raw.get("collection_problems", []) if item.get("outcome") in ("error", "skipped")
    ]
    if problems:
        for item in problems:
            print(f"error: {item['nodeid']}: {item['detail']}", file=sys.stderr)
        print("error: fix the collection problems first; the manifest was not changed", file=sys.stderr)
        return 2
    old = set(manifest["tests"])
    new = sorted(set(raw.get("collected", [])))
    manifest["tests"] = new
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    added = sorted(set(new) - old)
    removed = sorted(old - set(new))
    print(f"Updated {manifest_path}: {len(new)} tests, {len(added)} added, {len(removed)} removed.")
    for name in added:
        print(f"  + {name}")
    for name in removed:
        print(f"  - {name}")
    return 0


def _error_report(message: str) -> dict[str, Any]:
    report = _new_report("security-suite", "Security Regression Suite")
    report.update(
        status="error",
        summary=message,
        problems=[message],
        counts={},
        failed_tests=[],
        skipped_tests=[],
        collection_problems=[],
    )
    return report


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    pytest_args: list[str] = []
    if "--" in arguments:
        index = arguments.index("--")
        arguments, pytest_args = arguments[:index], arguments[index + 1 :]
    parser = argparse.ArgumentParser(
        description="Run the full test suite or the Security Regression Suite and apply its gate policy.",
        epilog="Pass extra pytest options after '--'.",
    )
    parser.add_argument("suite", choices=("full", "security"))
    parser.add_argument("--report", type=Path, help="write the JSON report to this file")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Security Regression Suite manifest (default: %(default)s)",
    )
    parser.add_argument(
        "--base-manifest",
        type=Path,
        help="manifest of the base commit; the report lists the tests the change removed or added",
    )
    parser.add_argument("--base-ref", help="name of the base commit, for the report")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-manifest", action="store_true", help="collect only and compare with the manifest"
    )
    mode.add_argument(
        "--update-manifest", action="store_true", help="rewrite the test list of the manifest"
    )
    args = parser.parse_args(arguments)
    root = args.root.resolve()

    if args.suite == "full":
        if args.check_manifest or args.update_manifest or args.base_manifest:
            parser.error("--check-manifest, --update-manifest and --base-manifest need the security suite")
        returncode, raw = run_pytest([], pytest_args, root)
        return finish(evaluate_full(raw, returncode), args.report)

    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    try:
        manifest_name = manifest_path.relative_to(root).as_posix()
    except ValueError:
        manifest_name = manifest_path.as_posix()
    try:
        manifest = load_manifest(manifest_path)
    except ManifestError as exc:
        return finish(_error_report(str(exc)), args.report)
    targets = [path for path in manifest["paths"] if (root / path).exists()]
    missing_paths = [path for path in manifest["paths"] if not (root / path).exists()]
    if not targets:
        return finish(_error_report("none of the manifest paths exists"), args.report)
    options = [*coverage_args(), *pytest_args]

    if args.update_manifest:
        returncode, raw = run_pytest(targets, options, root, collect_only=True)
        return update_manifest(manifest_path, manifest, raw, returncode, missing_paths)
    if args.check_manifest:
        returncode, raw = run_pytest(targets, options, root, collect_only=True)
        return finish(
            evaluate_collection(raw, returncode, manifest, manifest_name, missing_paths), args.report
        )

    base_manifest = None
    if args.base_manifest is not None:
        try:
            base_manifest = load_manifest(args.base_manifest)
        except ManifestError as exc:
            print(f"warning: the base manifest is not used: {exc}", file=sys.stderr)
    returncode, raw = run_pytest(targets, options, root)
    report = evaluate_security(
        raw,
        returncode,
        manifest,
        manifest_name,
        base_manifest=base_manifest,
        base_ref=args.base_ref,
        missing_paths=missing_paths,
    )
    return finish(report, args.report)


if __name__ == "__main__":
    sys.exit(main())
