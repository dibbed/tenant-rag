#!/usr/bin/env python3
"""Run one Static Analysis Check (Ruff, MyPy or Bandit) and write its report.

    python scripts/verification/static_analysis.py {ruff,mypy,bandit} [--mode MODE] [--report PATH]
    python scripts/verification/static_analysis.py pins TOOL [TOOL ...]

The checks use the repository's own tools and settings (pyproject.toml):

    ruff    style check             ruff check . --no-fix
    mypy    type check              mypy ragbot --ignore-missing-imports   (as `make type-check`)
    bandit  insecure-pattern check  bandit -c pyproject.toml -r ragbot     ([tool.bandit])

The exit status of the tool is kept: 0 when there is no finding, 1 when there
are findings, 2 when the tool could not run. MODE ("report-only" or
"blocking") is written to the report and sets the annotation level. In
.github/workflows/ci.yml a Report-Only Check runs with continue-on-error, so
findings mark the check as failed without blocking a merge.

"pins" prints the requirement of each tool pinned in the dev extra of
pyproject.toml, so CI installs the same versions as a developer environment.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parents[2]
MODES = ("report-only", "blocking")
MAX_FILE_ANNOTATIONS = 9
TOOLS: dict[str, dict[str, Any]] = {
    "ruff": {
        "title": "Style check (Ruff)",
        "args": ["ruff", "check", ".", "--no-fix", "--output-format", "json"],
    },
    "mypy": {
        "title": "Type check (MyPy)",
        "args": ["mypy", "ragbot", "--ignore-missing-imports", "--no-color-output", "--no-pretty"],
    },
    "bandit": {
        "title": "Insecure-pattern check (Bandit)",
        "args": ["bandit", "-c", "pyproject.toml", "-r", "ragbot", "-f", "json", "-q"],
    },
}
MYPY_ERROR = re.compile(
    r"^(?P<path>[^:\s][^:]*):(?P<line>\d+)(?::\d+)?: error: (?P<message>.*?)(?:  \[(?P<code>[a-z0-9-]+)\])?$"
)
MYPY_SUMMARY = re.compile(r"^(Found \d+ errors? in \d+ files?.*|Success: .*)$")


class ToolOutputError(ValueError):
    """The output of the tool cannot be read."""


def parse_ruff(stdout: str) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    try:
        items = json.loads(stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ToolOutputError(f"the ruff output is not JSON: {exc}") from exc
    if not isinstance(items, list):
        raise ToolOutputError("the ruff output is not a list of findings")
    by_code = Counter(str(item.get("code") or "syntax-error") for item in items)
    files = {str(item.get("filename")) for item in items}
    return len(items), {"by_code": dict(by_code.most_common()), "files": len(files)}, []


def parse_mypy(stdout: str) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    lines = stdout.splitlines()
    matches = [match for match in (MYPY_ERROR.match(line) for line in lines) if match]
    by_code = Counter(match.group("code") or "none" for match in matches)
    files = {match.group("path") for match in matches}
    summary = next((line for line in reversed(lines) if MYPY_SUMMARY.match(line)), "")
    without_code = [match.group(0) for match in matches if not match.group("code")]
    details = {
        "by_code": dict(by_code.most_common()),
        "files": len(files),
        "summary_line": summary,
        "errors_without_code": without_code[:10],
    }
    return len(matches), details, []


def _relative(path: str, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return path


def parse_bandit(stdout: str, root: Path = ROOT) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ToolOutputError(f"the bandit output is not JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ToolOutputError("the bandit output has no results list")
    results = data["results"]
    by_severity = Counter(str(result.get("issue_severity", "UNDEFINED")).upper() for result in results)
    by_test = Counter(f"{result.get('test_id')} {result.get('test_name')}" for result in results)
    notable = [
        {
            "severity": severity,
            "test": f"{result.get('test_id')} {result.get('test_name')}",
            "file": _relative(str(result.get("filename", "")), root),
            "line": int(result.get("line_number") or 0),
            "issue": str(result.get("issue_text", "")),
        }
        for severity in ("HIGH", "MEDIUM")
        for result in results
        if str(result.get("issue_severity", "")).upper() == severity
    ]
    details = {
        "by_severity": {level: by_severity.get(level, 0) for level in ("HIGH", "MEDIUM", "LOW")},
        "by_test": dict(by_test.most_common()),
        "high_and_medium": notable,
        "errors": data.get("errors", []),
    }
    annotations = [
        {
            "file": item["file"],
            "line": item["line"],
            "title": f"Bandit {item['test']} ({item['severity']})",
            "message": item["issue"],
        }
        for item in notable[:MAX_FILE_ANNOTATIONS]
    ]
    return len(results), details, annotations


PARSERS = {"ruff": parse_ruff, "mypy": parse_mypy, "bandit": parse_bandit}


def summarize(tool: str, count: int, details: dict[str, Any]) -> str:
    if tool == "ruff":
        top = ", ".join(f"{code} {number}" for code, number in list(details["by_code"].items())[:3])
        text = f"{count} findings in {details['files']} files"
        return f"{text} (most frequent: {top})" if count else text
    if tool == "mypy":
        return f"{count} errors in {details['files']} files"
    severity = details["by_severity"]
    return (
        f"{count} findings: {severity['HIGH']} high, {severity['MEDIUM']} medium, "
        f"{severity['LOW']} low severity"
    )


def tool_version(tool: str, runner: Callable[..., Any], root: Path) -> str:
    proc = runner(
        [sys.executable, "-m", tool, "--version"], cwd=root, capture_output=True, text=True, check=False
    )
    lines = (proc.stdout or proc.stderr or "").strip().splitlines()
    if not lines:
        return "unknown"
    # "python -m bandit --version" prints "__main__.py 1.7.9".
    return lines[0].replace("__main__.py", tool, 1)


def run_check(
    tool: str, mode: str, root: Path = ROOT, runner: Callable[..., Any] = subprocess.run
) -> dict[str, Any]:
    """Run one tool and build its report."""
    spec = TOOLS[tool]
    report: dict[str, Any] = {
        "schema": 1,
        "check": f"static-{tool}",
        "title": spec["title"],
        "tool": tool,
        "mode": mode,
        "command": " ".join(spec["args"]),
        "tool_version": tool_version(tool, runner, root),
        "python": platform.python_version(),
    }
    command = [sys.executable, "-m", *spec["args"]]
    print("+ " + " ".join(command), flush=True)
    proc = runner(command, cwd=root, capture_output=True, text=True, check=False)
    stdout = proc.stdout or ""
    warnings = [line for line in (proc.stderr or "").splitlines() if line.strip()][:20]
    try:
        count, details, annotations = PARSERS[tool](stdout)
    except ToolOutputError as exc:
        report.update(
            status="error",
            findings=None,
            summary=f"could not run: {exc}",
            problems=[str(exc), f"{tool} exited with code {proc.returncode}"],
            warnings=warnings,
            output_tail=stdout.splitlines()[-20:],
            tool_exit_code=proc.returncode,
        )
        return report
    problems = []
    if proc.returncode not in (0, 1):
        problems.append(f"{tool} exited with code {proc.returncode}")
        problems.extend(details.get("errors_without_code", [])[:5])
    elif proc.returncode == 1 and count == 0:
        problems.append(f"{tool} exited with code 1 but reported no finding")
    if problems:
        status = "error"
    elif count == 0:
        status = "pass"
    else:
        status = "fail" if mode == "blocking" else "findings"
    report.update(
        status=status,
        findings=count,
        summary=summarize(tool, count, details),
        details=details,
        problems=problems,
        warnings=warnings,
        annotations=annotations,
        tool_exit_code=proc.returncode,
    )
    return report


def exit_code(report: dict[str, Any]) -> int:
    """Keep the exit status of the tool: 0 no finding, 1 findings, 2 could not run."""
    return {"pass": 0, "findings": 1, "fail": 1}.get(report["status"], 2)


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def emit_annotations(report: dict[str, Any]) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true" or report["status"] == "pass":
        return
    level = "error" if report["mode"] == "blocking" or report["status"] == "error" else "warning"
    title = f"{report['title']} ({report['mode']})"
    lines = [report["summary"], *report.get("problems", [])]
    if report["mode"] == "report-only" and report["status"] != "error":
        lines.append("Report-Only Check: the findings do not block a merge.")
    print(f"::{level} title={_escape_property(title)}::{_escape_data(chr(10).join(lines))}", flush=True)
    for item in report.get("annotations", []):
        print(
            f"::{level} file={_escape_property(item['file'])},line={item['line']},"
            f"title={_escape_property(item['title'])}::{_escape_data(item['message'])}",
            flush=True,
        )


def print_report(report: dict[str, Any]) -> None:
    print()
    print(f"== {report['title']} ({report['mode']}): {report['status'].upper()} ==")
    print(f"{report.get('tool_version')}: {report['summary']}")
    for problem in report.get("problems", []):
        print(f"- {problem}")
    details = report.get("details") or {}
    for key in ("by_code", "by_severity", "by_test"):
        if details.get(key):
            print(f"{key}:")
            for name, number in list(details[key].items())[:25]:
                print(f"  {number:6d}  {name}")
    for item in details.get("high_and_medium", []):
        print(f"  {item['severity']:<6} {item['test']} {item['file']}:{item['line']} {item['issue']}")
    for warning in report.get("warnings", []):
        print(f"warning: {warning}")


def print_pins(tools: list[str], root: Path = ROOT) -> int:
    """Print the pinned requirement of each tool from the dev extra of pyproject.toml."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # Python 3.10: tomli is installed with pytest
        import tomli as tomllib
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dev = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    for tool in tools:
        pattern = re.compile(rf"^{re.escape(tool)}\s*==\s*[\w.]+$", re.IGNORECASE)
        matches = [requirement.strip() for requirement in dev if pattern.match(requirement.strip())]
        if len(matches) != 1:
            print(f"error: the dev extra of pyproject.toml has no exact pin for {tool}", file=sys.stderr)
            return 2
        print(matches[0])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one Static Analysis Check (Ruff, MyPy or Bandit) and write its report."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for tool, spec in TOOLS.items():
        command = commands.add_parser(tool, help=spec["title"])
        command.add_argument("--mode", choices=MODES, default="report-only")
        command.add_argument("--report", type=Path, help="write the JSON report to this file")
    pins = commands.add_parser("pins", help="print the pinned tool requirements from pyproject.toml")
    pins.add_argument("tools", nargs="+", choices=sorted(TOOLS))
    args = parser.parse_args(argv)
    if args.command == "pins":
        return print_pins(args.tools)
    report = run_check(args.command, args.mode)
    print_report(report)
    emit_annotations(report)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
