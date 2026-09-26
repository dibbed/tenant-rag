#!/usr/bin/env python3
"""Verification Summary (AC-MTS-CI-001.3): one table with every check of a pipeline run.

    python scripts/verification/summary.py --reports DIR [--needs-env NAME]
        [--python-versions 3.10,3.11,3.12] [--output FILE] [--allow-missing]

Reads the JSON reports that run_suite.py, static_analysis.py,
dependency_audit.py and container_check.py wrote into DIR, and writes a
Markdown summary to --output and, in GitHub Actions, to the job summary.
Exits 1 when a Blocking Check failed, had an error or has no report.
--allow-missing (for local runs) leaves out the checks that have no report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_VERSIONS = ("3.10", "3.11", "3.12")
STATIC_TOOLS = (
    ("ruff", "Style check (Ruff)"),
    ("mypy", "Type check (MyPy)"),
    ("bandit", "Insecure-pattern check (Bandit)"),
)
RESULTS = {"pass": "Passed", "fail": "Failed", "error": "Error", "findings": "Findings", "missing": "No report"}
MODES = {"blocking": "Blocking", "report-only": "Report-only"}
PER_VERSION = ("tests", "security-suite")
MAX_LISTED = 40


def minor_version(value: Any) -> str:
    return ".".join(str(value or "").split(".")[:2])


def load_reports(directory: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    """Check reports by (check, Python version); the version is empty for single checks."""
    reports: dict[tuple[str, str], dict[str, Any]] = {}
    problems: list[str] = []
    if not directory.is_dir():
        return reports, [f"report directory not found: {directory}"]
    for path in sorted(directory.rglob("*.json")):
        data, problem = _read(path)
        if problem:
            problems.append(problem)
        if not isinstance(data, dict) or "check" not in data or "status" not in data:
            continue
        check = str(data["check"])
        version = minor_version(data.get("python")) if check in PER_VERSION else ""
        reports[(check, version)] = data
    return reports, problems


def _read(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, f"{path.name} could not be read: {exc}"


def expected_checks(versions: list[str]) -> list[dict[str, Any]]:
    rows = [
        {"key": ("tests", v), "title": f"Tests (Python {v})", "mode": "blocking", "job": "tests"}
        for v in versions
    ]
    rows += [
        {
            "key": ("security-suite", v),
            "title": f"Security Regression Suite (Python {v})",
            "mode": "blocking",
            "job": "security-suite",
        }
        for v in versions
    ]
    rows += [
        {"key": (f"static-{tool}", ""), "title": title, "mode": None, "job": "static-analysis"}
        for tool, title in STATIC_TOOLS
    ]
    rows.append(
        {
            "key": ("dependency-audit", ""),
            "title": "Dependency Vulnerability Check",
            "mode": "blocking",
            "job": "dependency-audit",
        }
    )
    rows.append({"key": ("container", ""), "title": "Container Build Check", "mode": "blocking", "job": "container"})
    return rows


def short_id(nodeid: str) -> str:
    return nodeid.rsplit("/", 1)[-1]


def describe(report: dict[str, Any]) -> str:
    """The Findings/Details text of one report."""
    check = str(report.get("check", ""))
    text = str(report.get("summary") or "")
    if check == "tests":
        skipped = report.get("skipped_tests") or []
        if skipped:
            names = ", ".join(short_id(str(item.get("nodeid", ""))) for item in skipped[:2])
            more = f" and {len(skipped) - 2} more" if len(skipped) > 2 else ""
            text += f" (skipped: {names}{more})"
    elif check == "security-suite":
        manifest = report.get("manifest") or {}
        parts = [text, f"manifest {manifest.get('expected', 0)} tests"]
        if manifest.get("missing"):
            parts.append(f"{len(manifest['missing'])} missing")
        if manifest.get("unexpected"):
            parts.append(f"{len(manifest['unexpected'])} not in the manifest")
        removed = manifest.get("removed_vs_base") or []
        added = manifest.get("added_vs_base") or []
        if removed or added:
            parts.append(f"this change removes {len(removed)} and adds {len(added)} security tests")
        elif manifest.get("base_available"):
            parts.append("no manifest change")
        text = "; ".join(part for part in parts if part)
    if report.get("status") in ("fail", "error") and report.get("problems"):
        text += ". " + "; ".join(str(problem) for problem in report["problems"][:3])
    return text


def build_rows(
    reports: dict[tuple[str, str], dict[str, Any]],
    versions: list[str],
    needs: dict[str, Any],
    allow_missing: bool,
) -> list[dict[str, Any]]:
    rows = []
    for spec in expected_checks(versions):
        report = reports.get(spec["key"])
        mode = spec["mode"] or (report or {}).get("mode") or "report-only"
        if report is None:
            if allow_missing:
                continue
            result = (needs.get(spec["job"]) or {}).get("result", "unknown")
            rows.append({**spec, "mode": mode, "status": "missing", "details": f"no report (job result: {result})", "report": None})
            continue
        rows.append({**spec, "mode": mode, "status": str(report.get("status")), "details": describe(report), "report": report})
    return rows


def gate_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Blocking Checks that did not pass."""
    return [row for row in rows if row["mode"] == "blocking" and row["status"] != "pass"]


def cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _context_line() -> str:
    sha = os.environ.get("GITHUB_SHA", "")[:12]
    if not sha:
        return ""
    parts = [f"Commit `{sha}`", f"event `{os.environ.get('GITHUB_EVENT_NAME', '')}`"]
    server, repository, run = (os.environ.get(name, "") for name in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    if server and repository and run:
        parts.append(f"[workflow run]({server}/{repository}/actions/runs/{run})")
    return ", ".join(parts)


def _section_failures(failures: list[dict[str, Any]]) -> list[str]:
    if not failures:
        return []
    lines = ["### Failed Blocking Checks", ""]
    for row in failures:
        problems = (row["report"] or {}).get("problems") or [row["details"]]
        lines.append(f"- **{cell(row['title'])}**: " + "; ".join(cell(problem) for problem in problems))
    return [*lines, ""]


def _listing(title: str, items: list[str]) -> list[str]:
    if not items:
        return []
    lines = ["", f"**{title} ({len(items)}):**", ""]
    lines += [f"- {cell(item)}" for item in items[:MAX_LISTED]]
    if len(items) > MAX_LISTED:
        lines.append(f"- ... and {len(items) - MAX_LISTED} more")
    return lines


def _section_security(rows: list[dict[str, Any]]) -> list[str]:
    runs = [row for row in rows if row["key"][0] == "security-suite" and row["report"]]
    if not runs:
        return []
    first = runs[0]["report"].get("manifest") or {}
    lines = [
        "### Security Regression Suite",
        "",
        f"Manifest `{first.get('path', 'tests/security/suite_manifest.json')}`: "
        f"{first.get('expected', 0)} tests in {len(first.get('paths', []))} paths.",
    ]
    if first.get("base_available"):
        removed = first.get("removed_vs_base") or []
        added = first.get("added_vs_base") or []
        if not removed and not added:
            lines.append(f"This change removes and adds no security test (base `{first.get('base_ref')}`).")
        lines += _listing("Security tests removed from the manifest by this change", removed)
        lines += _listing("Security tests added to the manifest by this change", added)
    else:
        lines.append("No base manifest was available, so manifest changes are not compared.")
    failed, skipped, missing, unexpected = [], [], set(), set()
    for row in runs:
        report = row["report"]
        version = row["key"][1]
        failed += [f"{item['nodeid']} (Python {version}): {item.get('message', '')}" for item in report.get("failed_tests", [])]
        skipped += [f"{item['nodeid']} (Python {version}): {item.get('reason', '')}" for item in report.get("skipped_tests", [])]
        manifest = report.get("manifest") or {}
        missing.update(manifest.get("missing") or [])
        unexpected.update(manifest.get("unexpected") or [])
    lines += _listing("Failed security tests", failed)
    lines += _listing("Skipped security tests (not allowed)", skipped)
    lines += _listing("Security tests in the manifest but not collected (removed or renamed)", sorted(missing))
    lines += _listing("Collected security tests that are not in the manifest", sorted(unexpected))
    return [*lines, ""]


def _advisory_table(advisories: list[dict[str, Any]]) -> list[str]:
    lines = ["", "| Package | Version | Advisory | Severity | Fixed in | Summary |", "|---|---|---|---|---|---|"]
    lines += [
        f"| {cell(a['package'])} | {cell(a['version'])} | {cell(a['id'])} | {cell(a['severity'])} | "
        f"{cell(', '.join(a.get('fix_versions') or []) or 'no fixed version')} | {cell(a.get('summary', ''))} |"
        for a in advisories[:100]
    ]
    return lines


def _section_dependencies(report: dict[str, Any] | None) -> list[str]:
    if not report:
        return []
    lines = [
        "### Dependency Vulnerability Check",
        "",
        f"{cell(report.get('summary', ''))}. Tool: {cell(report.get('tool', 'pip-audit'))}, "
        f"Python {cell(report.get('python', ''))}. Blocking: {str(report.get('fail_on', 'high')).upper()} "
        "or higher, and unknown severity.",
    ]
    blocking = report.get("blocking") or []
    accepted = report.get("accepted") or []
    reported = report.get("non_blocking") or []
    lines += ["", f"**Blocking advisories ({len(blocking)}):**" if blocking else "Blocking advisories: none."]
    if blocking:
        lines += _advisory_table(blocking)
    lines += ["", f"**Accepted exceptions ({len(accepted)}):**" if accepted else "Accepted exceptions: none."]
    if accepted:
        lines += [
            "",
            "| Advisory | Package | Version | Severity | Owner | Review by | Justification | Mitigation |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for advisory in accepted:
            exception = advisory.get("exception") or {}
            lines.append(
                f"| {cell(advisory['id'])} | {cell(advisory['package'])} | {cell(advisory['version'])} | "
                f"{cell(advisory['severity'])} | {cell(exception.get('owner', ''))} | {cell(exception.get('review_by', ''))} | "
                f"{cell(exception.get('justification', ''))} | {cell(exception.get('mitigation', ''))} |"
            )
    exceptions = report.get("exceptions") or {}
    lines += _listing(
        "Invalid exception entries",
        [f"{item.get('id')} ({item.get('package')}): {'; '.join(item.get('problems', []))}" for item in exceptions.get("invalid") or []],
    )
    lines += _listing(
        "Unused exception entries",
        [f"{item.get('id')} ({item.get('package')} {item.get('version')})" for item in exceptions.get("unused") or []],
    )
    if reported:
        lines += ["", f"<details><summary>Non-blocking advisories ({len(reported)})</summary>"]
        lines += _advisory_table(reported)
        lines += ["", "</details>"]
    return [*lines, ""]


def _section_container(report: dict[str, Any] | None) -> list[str]:
    if not report:
        return []
    lines = ["### Container Build Check", "", "| Step | Result | Details |", "|---|---|---|"]
    lines += [
        f"| {cell(step.get('step'))} | {RESULTS.get(str(step.get('status')), cell(step.get('status')))} | {cell(step.get('detail'))} |"
        for step in report.get("steps", [])
    ]
    details = report.get("details") or {}
    if details.get("uid") is not None:
        user = details.get("runtime_user") or details.get("image_user") or "not set"
        lines += ["", f"Runtime user: UID {details['uid']} (USER {cell(user)})."]
    if report.get("status") != "pass" and report.get("log_tail"):
        lines += ["", "<details><summary>Container log (last lines)</summary>", "", "```text"]
        lines += [str(line) for line in report["log_tail"][-80:]]
        lines += ["```", "", "</details>"]
    return [*lines, ""]


def _section_static(rows: list[dict[str, Any]]) -> list[str]:
    static = [row for row in rows if row["key"][0].startswith("static-")]
    if not static:
        return []
    lines = ["### Static Analysis", ""]
    for row in static:
        report = row["report"] or {}
        version = f" ({cell(report['tool_version'])})" if report.get("tool_version") else ""
        lines.append(f"- **{cell(row['title'])}**{version}, {MODES.get(row['mode'], row['mode'])}: {cell(row['details'])}")
    lines += [
        "",
        "A Report-Only Check does not block a merge. To make one a Blocking Check, set its `mode` to "
        "`blocking` in the `static-analysis` matrix of `.github/workflows/ci.yml` and add "
        "`Static Analysis (<tool>, blocking)` to the required status checks of `main`.",
    ]
    return [*lines, ""]


def render(
    rows: list[dict[str, Any]],
    reports: dict[tuple[str, str], dict[str, Any]],
    versions: list[str],
    read_problems: list[str],
) -> str:
    """The Markdown Verification Summary."""
    failures = gate_failures(rows)
    lines = ["## Verification Summary", ""]
    context = _context_line()
    if context:
        lines += [context, ""]
    if failures:
        names = ", ".join(row["title"] for row in failures)
        lines.append(f"**Result: FAILED.** {len(failures)} Blocking Check(s) did not pass: {names}.")
    else:
        lines.append("**Result: PASSED.** Every Blocking Check passed.")
    lines += ["", f"Python versions: {', '.join(versions)}.", ""]
    lines += ["| Check | Mode | Result | Findings/Details |", "|---|---|---|---|"]
    lines += [
        f"| {cell(row['title'])} | {MODES.get(row['mode'], row['mode'])} | {RESULTS.get(row['status'], cell(row['status']))} | {cell(row['details'])} |"
        for row in rows
    ]
    lines.append("")
    lines += _section_failures(failures)
    lines += _section_security(rows)
    lines += _section_dependencies(reports.get(("dependency-audit", "")))
    lines += _section_container(reports.get(("container", "")))
    lines += _section_static(rows)
    if read_problems:
        lines += ["### Report problems", "", *[f"- {cell(problem)}" for problem in read_problems], ""]
    return "\n".join(lines) + "\n"


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def annotate(level: str, title: str, message: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::{level} title={_escape_property(title)}::{_escape_data(message)}", flush=True)


def emit_annotations(rows: list[dict[str, Any]]) -> None:
    failures = gate_failures(rows)
    if failures:
        annotate("error", "Verification Summary", "FAILED: " + ", ".join(row["title"] for row in failures))
        for row in failures[:9]:
            annotate("error", row["title"], row["details"])
    else:
        annotate(
            "notice",
            "Verification Summary",
            "PASSED. " + "; ".join(f"{row['title']}: {RESULTS.get(row['status'], row['status'])}" for row in rows),
        )
    removed = sorted(
        {
            name
            for row in rows
            if row["key"][0] == "security-suite" and row["report"]
            for name in (row["report"].get("manifest") or {}).get("removed_vs_base") or []
        }
    )
    if removed:
        annotate("warning", "Security tests removed by this change", "\n".join(removed[:MAX_LISTED]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the Verification Summary of one pipeline run.")
    parser.add_argument("--reports", type=Path, required=True, help="directory with the check reports")
    parser.add_argument("--needs-env", help="environment variable that holds the toJSON(needs) of the workflow")
    parser.add_argument("--python-versions", default=",".join(DEFAULT_VERSIONS))
    parser.add_argument("--output", type=Path, help="also write the Markdown summary to this file")
    parser.add_argument("--allow-missing", action="store_true", help="leave out checks without a report")
    args = parser.parse_args(argv)
    versions = [version.strip() for version in args.python_versions.split(",") if version.strip()]
    needs: dict[str, Any] = {}
    if args.needs_env and os.environ.get(args.needs_env):
        try:
            needs = json.loads(os.environ[args.needs_env])
        except ValueError:
            needs = {}
    reports, read_problems = load_reports(args.reports)
    rows = build_rows(reports, versions, needs, args.allow_missing)
    markdown = render(rows, reports, versions, read_problems)
    print(markdown)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)
    emit_annotations(rows)
    return 1 if gate_failures(rows) else 0


if __name__ == "__main__":
    sys.exit(main())
