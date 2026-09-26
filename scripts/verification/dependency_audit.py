#!/usr/bin/env python3
"""Dependency Vulnerability Check (REQ-MTS-CI-004).

    python scripts/verification/dependency_audit.py run --pip-audit PATH
        [--python PYTHON] [--exceptions FILE] [--fail-on LEVEL] [--report PATH]
    python scripts/verification/dependency_audit.py classify --input FILE
        [--osv-records FILE] [--exceptions FILE] [--fail-on LEVEL] [--report PATH]
    python scripts/verification/dependency_audit.py validate-exceptions [--exceptions FILE]

"run" audits every package installed for PYTHON (default: this interpreter)
with pip-audit and the OSV advisory database. pip-audit runs from its own
virtual environment (--pip-audit), so its own dependencies are not audited.
"classify" applies the policy to an existing pip-audit JSON report.

Policy:

- An advisory with severity HIGH or CRITICAL fails the check (--fail-on
  changes the threshold). The severity comes from the GitHub-reviewed
  advisory (GHSA) in OSV; without one, from a CVSS v3 vector in OSV.
- An advisory whose severity cannot be found fails the check (fail closed).
- An accepted exception stops one advisory from failing the check. The entry
  names the advisory (id or alias), the package and its installed version,
  and gives a justification, a mitigation, an owner and a review date that
  has not passed and is at most 366 days away. The report and the
  Verification Summary list every accepted exception. An invalid entry fails
  the check. An entry that matches no advisory is reported as unused.
- MODERATE and LOW advisories are reported and do not fail the check.
- A package that pip-audit could not audit fails the check, except the
  project itself (installed in editable mode).

Exit codes: 0 passed, 1 failed, 2 tool or network error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXCEPTIONS = Path(".github/dependency-audit-exceptions.json")
OSV_VULN_URL = "https://api.osv.dev/v1/vulns/"
SEVERITY_RANK = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}
FAIL_ON = {"low": 1, "moderate": 2, "high": 3, "critical": 4}
MAX_REVIEW_DAYS = 366
REQUIRED_FIELDS = ("id", "package", "version", "justification", "mitigation", "owner", "review_by")
PLACEHOLDERS = frozenset(
    {"", "-", "?", "n/a", "na", "none", "null", "tbd", "todo", "fixme", "unknown", "owner", "someone", "nobody", "xxx"}
)
ADVISORY_ID = re.compile(
    r"^(GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}|PYSEC-\d{4}-\d+|CVE-\d{4}-\d{4,}|OSV-\d{4}-\d+|MAL-\d{4}-\d+)$",
    re.IGNORECASE,
)
PROJECT_NAMES = frozenset({"tenant-rag"})
FETCHED_PREFIXES = ("GHSA-", "PYSEC-", "OSV-", "MAL-")
CIA = {"H": 0.56, "L": 0.22, "N": 0.0}
ATTACK_VECTOR = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
ATTACK_COMPLEXITY = {"L": 0.77, "H": 0.44}
USER_INTERACTION = {"N": 0.85, "R": 0.62}
MAX_ANNOTATION_ITEMS = 25


def canonical_name(name: str) -> str:
    """Normalized package name (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _roundup(value: float) -> float:
    scaled = round(value * 100000)
    if scaled % 10000 == 0:
        return scaled / 100000.0
    return (math.floor(scaled / 10000) + 1) / 10.0


def cvss3_base_score(vector: str) -> float:
    """Base score of a CVSS v3.0 or v3.1 vector (FIRST specification)."""
    if not vector.startswith("CVSS:3."):
        raise ValueError(f"not a CVSS v3 vector: {vector}")
    metrics = dict(part.split(":", 1) for part in vector.split("/")[1:])
    changed = metrics["S"] == "C"
    privileges = {"N": 0.85, "L": 0.68 if changed else 0.62, "H": 0.5 if changed else 0.27}[metrics["PR"]]
    iss = 1 - (1 - CIA[metrics["C"]]) * (1 - CIA[metrics["I"]]) * (1 - CIA[metrics["A"]])
    if changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    else:
        impact = 6.42 * iss
    exploitability = (
        8.22
        * ATTACK_VECTOR[metrics["AV"]]
        * ATTACK_COMPLEXITY[metrics["AC"]]
        * privileges
        * USER_INTERACTION[metrics["UI"]]
    )
    if impact <= 0:
        return 0.0
    total = 1.08 * (impact + exploitability) if changed else impact + exploitability
    return _roundup(min(total, 10.0))


def severity_from_score(score: float) -> str:
    """Qualitative severity of a CVSS v3 base score."""
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MODERATE"
    return "LOW"


def record_severity(record: Any) -> str | None:
    """Severity of one OSV record, or None when the record gives none."""
    if not isinstance(record, dict) or record.get("_error") or record.get("_missing"):
        return None
    database = record.get("database_specific")
    value = database.get("severity") if isinstance(database, dict) else None
    if isinstance(value, str) and value.strip():
        level = value.strip().upper()
        level = "MODERATE" if level == "MEDIUM" else level
        if level in SEVERITY_RANK:
            return level
    for entry in record.get("severity") or []:
        if not isinstance(entry, dict) or entry.get("type") != "CVSS_V3":
            continue
        score = entry.get("score")
        if isinstance(score, str):
            try:
                return severity_from_score(cvss3_base_score(score))
            except (KeyError, ValueError):
                continue
    return None


def _highest(levels: Iterable[str | None]) -> str | None:
    known = [level for level in levels if level]
    return max(known, key=SEVERITY_RANK.__getitem__) if known else None


def advisory_severity(ids: set[str], records: dict[str, Any]) -> tuple[str, str]:
    """(severity, source) for one advisory and all of its aliases."""
    ordered = sorted(ids)
    reviewed = _highest(record_severity(records.get(i)) for i in ordered if i.upper().startswith("GHSA-"))
    if reviewed:
        return reviewed, "GitHub advisory"
    other = _highest(record_severity(records.get(i)) for i in ordered)
    if other:
        return other, "OSV record"
    return "UNKNOWN", "not found"


def advisory_summary(ids: set[str], records: dict[str, Any]) -> str:
    """Short summary of an advisory from its OSV records."""
    ordered = sorted(ids, key=id_preference)
    for key in ("summary", "details"):
        for identifier in ordered:
            record = records.get(identifier)
            text = record.get(key) if isinstance(record, dict) else None
            if isinstance(text, str) and text.strip():
                line = " ".join(text.split())
                return line if len(line) <= 160 else line[:157] + "..."
    return ""


def id_preference(identifier: str) -> tuple[int, str]:
    """Sort key: GitHub advisory ids first, then PyPI, then CVE, then others."""
    upper = identifier.upper()
    for rank, prefix in enumerate(("GHSA-", "PYSEC-", "CVE-")):
        if upper.startswith(prefix):
            return rank, upper
    return 3, upper


def _fetch_once(identifier: str, timeout: float) -> dict[str, Any]:
    url = OSV_VULN_URL + urllib.parse.quote(identifier, safe="")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"_missing": True}
        return {"_retry": f"HTTP {exc.code}"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"_retry": f"{type(exc).__name__}: {exc}"}
    return data if isinstance(data, dict) else {"_error": "unexpected OSV response"}


def fetch_osv_record(identifier: str, attempts: int = 4, timeout: float = 30.0) -> dict[str, Any]:
    """One OSV record; {'_missing': True} for an unknown id, {'_error': ...} on failure."""
    last_error = "not fetched"
    for attempt in range(attempts):
        result = _fetch_once(identifier, timeout)
        if "_retry" not in result:
            return result
        last_error = result["_retry"]
        time.sleep(min(2**attempt, 10))
    return {"_error": last_error}


def offline_fetch(records: dict[str, Any]) -> Callable[[str], dict[str, Any]]:
    """Fetch function that reads OSV records from a local JSON object instead of the network."""

    def fetch(identifier: str) -> dict[str, Any]:
        return records.get(identifier, {"_missing": True})

    return fetch


def fetch_records(
    ids: set[str], fetch: Callable[[str], dict[str, Any]], workers: int = 8
) -> dict[str, dict[str, Any]]:
    ordered = sorted(ids)
    if not ordered:
        return {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(fetch, ordered))
    return dict(zip(ordered, results, strict=True))


def parse_pip_audit(data: Any) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """(audited dependencies, skipped dependencies) from pip-audit JSON output."""
    dependencies = data.get("dependencies") if isinstance(data, dict) else data
    if not isinstance(dependencies, list):
        raise ValueError("the pip-audit output has no 'dependencies' list")
    if not all(isinstance(dep, dict) and "name" in dep for dep in dependencies):
        raise ValueError("the pip-audit output has a dependency without a name")
    resolved = [dep for dep in dependencies if "skip_reason" not in dep]
    skipped = [
        {"name": str(dep["name"]), "reason": str(dep.get("skip_reason", ""))}
        for dep in dependencies
        if "skip_reason" in dep
    ]
    return resolved, skipped


def group_advisories(resolved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per package and advisory; findings that share an id or alias are merged."""
    advisories: list[dict[str, Any]] = []
    for dep in resolved:
        groups: list[dict[str, Any]] = []
        for vuln in dep.get("vulns") or []:
            ids = {str(vuln.get("id") or "")} | {str(alias) for alias in vuln.get("aliases") or []}
            ids.discard("")
            merged = {
                "package": str(dep["name"]),
                "version": str(dep.get("version", "")),
                "ids": set(ids),
                "fix_versions": {str(version) for version in vuln.get("fix_versions") or []},
            }
            for group in [group for group in groups if group["ids"] & ids]:
                merged["ids"] |= group["ids"]
                merged["fix_versions"] |= group["fix_versions"]
                groups.remove(group)
            groups.append(merged)
        advisories.extend(groups)
    for advisory in advisories:
        advisory["id"] = sorted(advisory["ids"], key=id_preference)[0]
    return advisories


def load_exceptions(path: Path) -> tuple[list[Any], list[str]]:
    """(entries, problems of the file itself)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], [f"exceptions file not found: {path}"]
    except (OSError, ValueError) as exc:
        return [], [f"exceptions file is not valid JSON: {exc}"]
    if not isinstance(data, dict) or not isinstance(data.get("exceptions"), list):
        return [], ["the exceptions file must be a JSON object with an 'exceptions' list"]
    return list(data["exceptions"]), []


def validate_exception(entry: Any, today: dt.date) -> list[str]:
    """Problems of one exception entry (an empty list means valid)."""
    if not isinstance(entry, dict):
        return ["the entry must be a JSON object"]
    problems = [
        f"'{field}' is missing or a placeholder"
        for field in REQUIRED_FIELDS
        if not isinstance(entry.get(field), str) or entry[field].strip().lower() in PLACEHOLDERS
    ]
    identifier = entry.get("id")
    if isinstance(identifier, str) and identifier.strip() and not ADVISORY_ID.match(identifier.strip()):
        problems.append(f"'id' is not an advisory id: {identifier!r}")
    version = entry.get("version")
    if isinstance(version, str) and any(char in version for char in "*<>=~^, "):
        problems.append("'version' must be one exact installed version")
    review = entry.get("review_by")
    if isinstance(review, str) and review.strip().lower() not in PLACEHOLDERS:
        try:
            date = dt.date.fromisoformat(review.strip())
        except ValueError:
            problems.append(f"'review_by' is not a date (YYYY-MM-DD): {review!r}")
        else:
            if date < today:
                problems.append(f"expired: the review date {date.isoformat()} has passed")
            elif (date - today).days > MAX_REVIEW_DAYS:
                problems.append(f"'review_by' is more than {MAX_REVIEW_DAYS} days away")
    return problems


def _entry_key(entry: Any) -> tuple[str, str, str] | None:
    if not isinstance(entry, dict):
        return None
    return (
        canonical_name(str(entry.get("package", ""))),
        str(entry.get("id", "")).strip().upper(),
        str(entry.get("version", "")).strip(),
    )


def match_exceptions(
    advisories: list[dict[str, Any]], entries: list[Any], today: dt.date
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Attach valid exceptions to advisories; return (invalid, unused, number of valid entries)."""
    invalid: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(entries):
        problems = validate_exception(entry, today)
        key = _entry_key(entry)
        if key is not None and key in seen:
            problems.append("duplicate entry")
        if key is not None:
            seen.add(key)
        if problems:
            invalid.append(
                {
                    "index": index,
                    "id": entry.get("id") if isinstance(entry, dict) else None,
                    "package": entry.get("package") if isinstance(entry, dict) else None,
                    "problems": problems,
                }
            )
        else:
            valid.append(entry)
    used: set[int] = set()
    for advisory in advisories:
        ids = {identifier.upper() for identifier in advisory["ids"]}
        for number, entry in enumerate(valid):
            if (
                canonical_name(entry["package"]) == canonical_name(advisory["package"])
                and entry["version"].strip() == advisory["version"]
                and entry["id"].strip().upper() in ids
            ):
                advisory["exception"] = {field: entry[field].strip() for field in REQUIRED_FIELDS}
                used.add(number)
                break
    unused = [
        {field: entry[field] for field in ("id", "package", "version", "owner", "review_by")}
        for number, entry in enumerate(valid)
        if number not in used
    ]
    return invalid, unused, len(valid)


def _sort_key(advisory: dict[str, Any]) -> tuple[int, str, str]:
    return -SEVERITY_RANK.get(advisory["severity"], 5), advisory["package"], advisory["id"]


def _view(advisory: dict[str, Any]) -> dict[str, Any]:
    return {
        "package": advisory["package"],
        "version": advisory["version"],
        "id": advisory["id"],
        "aliases": sorted(i for i in advisory["ids"] if i != advisory["id"]),
        "severity": advisory["severity"],
        "severity_source": advisory["severity_source"],
        "fix_versions": sorted(advisory["fix_versions"]),
        "summary": advisory.get("summary", ""),
        "exception": advisory.get("exception"),
    }


def audit(
    data: Any,
    *,
    fetch: Callable[[str], dict[str, Any]],
    exceptions: list[Any],
    today: dt.date,
    exceptions_problems: list[str] | None = None,
    fail_on: str = "high",
    tool: str = "pip-audit (OSV)",
    python: str | None = None,
    exceptions_path: str = DEFAULT_EXCEPTIONS.as_posix(),
) -> dict[str, Any]:
    """Apply the policy to pip-audit output and return the report."""
    report: dict[str, Any] = {
        "schema": 1,
        "check": "dependency-audit",
        "title": "Dependency Vulnerability Check",
        "mode": "blocking",
        "tool": tool,
        "python": python or platform.python_version(),
        "fail_on": fail_on,
    }
    try:
        resolved, skipped = parse_pip_audit(data)
    except ValueError as exc:
        report.update(
            status="error",
            summary=f"the pip-audit output cannot be read: {exc}",
            problems=[str(exc)],
            counts={},
            blocking=[],
            accepted=[],
            non_blocking=[],
            packages=[],
            skipped=[],
            exceptions={"path": exceptions_path, "valid": 0, "invalid": [], "unused": []},
            lookup_errors=[],
        )
        return report
    advisories = group_advisories(resolved)
    wanted = {advisory["id"] for advisory in advisories} | {
        identifier
        for advisory in advisories
        for identifier in advisory["ids"]
        if identifier.upper().startswith(FETCHED_PREFIXES)
    }
    records = fetch_records(wanted, fetch)
    lookup_errors = sorted(
        identifier for identifier, record in records.items() if isinstance(record, dict) and record.get("_error")
    )
    for advisory in advisories:
        advisory["severity"], advisory["severity_source"] = advisory_severity(advisory["ids"], records)
        advisory["summary"] = advisory_summary(advisory["ids"], records)
        advisory["lookup_failed"] = advisory["severity"] == "UNKNOWN" and bool(
            advisory["ids"] & set(lookup_errors)
        )
    invalid, unused, valid_count = match_exceptions(advisories, exceptions, today)
    threshold = FAIL_ON[fail_on]
    accepted = sorted((a for a in advisories if a.get("exception")), key=_sort_key)
    blocking = sorted(
        (
            a
            for a in advisories
            if not a.get("exception")
            and (a["severity"] == "UNKNOWN" or SEVERITY_RANK[a["severity"]] >= threshold)
        ),
        key=_sort_key,
    )
    non_blocking = sorted(
        (a for a in advisories if not a.get("exception") and a not in blocking), key=_sort_key
    )
    unaudited = [item for item in skipped if canonical_name(item["name"]) not in PROJECT_NAMES]
    problems: list[str] = []
    if blocking:
        problems.append(
            f"{len(blocking)} advisory(ies) of severity {fail_on.upper()} or higher, or of unknown "
            "severity, without an accepted exception"
        )
    if invalid:
        problems.append(f"{len(invalid)} invalid exception entry(ies)")
    problems.extend(exceptions_problems or [])
    if unaudited:
        names = ", ".join(item["name"] for item in unaudited)
        problems.append(f"{len(unaudited)} package(s) could not be audited: {names}")
    failed_lookups = [advisory for advisory in blocking if advisory["lookup_failed"]]
    if failed_lookups:
        problems.append(
            f"the OSV lookup failed for {len(failed_lookups)} advisory(ies), so their severity is unknown"
        )
    counts = Counter(advisory["severity"] for advisory in advisories)
    packages = sorted(f"{dep['name']}=={dep.get('version', '')}" for dep in resolved)
    status = "error" if failed_lookups else ("fail" if problems else "pass")
    report.update(
        status=status,
        summary=(
            f"{len(packages)} packages audited: {len(blocking)} blocking, {len(accepted)} accepted, "
            f"{len(non_blocking)} non-blocking advisories"
        ),
        counts={level: counts.get(level, 0) for level in ("CRITICAL", "HIGH", "MODERATE", "LOW", "UNKNOWN")},
        blocking=[_view(a) for a in blocking],
        accepted=[_view(a) for a in accepted],
        non_blocking=[_view(a) for a in non_blocking],
        packages=packages,
        skipped=skipped,
        exceptions={"path": exceptions_path, "valid": valid_count, "invalid": invalid, "unused": unused},
        problems=problems,
        lookup_errors=lookup_errors,
    )
    return report


def interpreter_info(python: str) -> tuple[list[str], str]:
    """(site-packages directories, Python version) of an interpreter."""
    code = (
        "import json, platform, sysconfig; p = sysconfig.get_paths(); "
        "print(json.dumps({'paths': sorted({p['purelib'], p['platlib']}), 'version': platform.python_version()}))"
    )
    output = subprocess.run([python, "-c", code], capture_output=True, text=True, check=True).stdout
    info = json.loads(output)
    return [path for path in info["paths"] if Path(path).is_dir()], str(info["version"])


def run_pip_audit(pip_audit: str, paths: list[str], output: Path) -> subprocess.CompletedProcess[str]:
    command = [pip_audit]
    for path in paths:
        command += ["--path", path]
    command += [
        "--skip-editable",
        "--vulnerability-service",
        "osv",
        "--format",
        "json",
        "--output",
        str(output),
        "--aliases",
        "on",
        "--desc",
        "off",
        "--progress-spinner",
        "off",
        "--timeout",
        "30",
    ]
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def annotate(level: str, title: str, items: list[str]) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true" or not items:
        return
    shown = list(items[:MAX_ANNOTATION_ITEMS])
    if len(items) > len(shown):
        shown.append(f"... and {len(items) - len(shown)} more (see the job log and the report)")
    print(f"::{level} title={_escape_property(title)}::{_escape_data(chr(10).join(shown))}", flush=True)


def _line(advisory: dict[str, Any]) -> str:
    fixes = ", ".join(advisory["fix_versions"]) or "no fixed version"
    return (
        f"{advisory['severity']:<8} {advisory['package']}=={advisory['version']} {advisory['id']} "
        f"(fixed in: {fixes}) {advisory['summary']}"
    )


def print_report(report: dict[str, Any]) -> None:
    print()
    print(f"== {report['title']}: {report['status'].upper()} ==")
    print(f"{report.get('tool')}, Python {report.get('python')}: {report.get('summary')}")
    for problem in report.get("problems", []):
        print(f"- {problem}")
    for title, key in (
        ("Blocking advisories", "blocking"),
        ("Accepted exceptions", "accepted"),
        ("Non-blocking advisories", "non_blocking"),
    ):
        items = report.get(key, [])
        print(f"{title} ({len(items)}):")
        for advisory in items:
            print(f"  {_line(advisory)}")
            exception = advisory.get("exception")
            if exception:
                print(f"      owner {exception['owner']}, review by {exception['review_by']}: {exception['justification']}")
    exceptions = report.get("exceptions", {})
    for item in exceptions.get("invalid", []):
        print(f"Invalid exception {item.get('id')} ({item.get('package')}): {'; '.join(item['problems'])}")
    for item in exceptions.get("unused", []):
        print(f"Unused exception {item['id']} ({item['package']} {item['version']})")


def emit_annotations(report: dict[str, Any]) -> None:
    annotate("error", "Dependency Vulnerability Check: blocking advisories", [_line(a) for a in report.get("blocking", [])])
    exceptions = report.get("exceptions", {})
    annotate(
        "error",
        "Dependency Vulnerability Check: invalid exceptions",
        [f"{item.get('id')} ({item.get('package')}): {'; '.join(item['problems'])}" for item in exceptions.get("invalid", [])],
    )
    annotate(
        "warning",
        "Dependency Vulnerability Check: unused exceptions",
        [f"{item['id']} ({item['package']} {item['version']})" for item in exceptions.get("unused", [])],
    )
    annotate(
        "notice",
        "Dependency Vulnerability Check: accepted exceptions",
        [
            f"{a['id']} ({a['package']} {a['version']}, {a['severity']}): owner {a['exception']['owner']}, "
            f"review by {a['exception']['review_by']}"
            for a in report.get("accepted", [])
        ],
    )
    if report["status"] == "error":
        annotate("error", "Dependency Vulnerability Check", list(report.get("problems", [])))


def _error(message: str, report_path: Path | None) -> int:
    report = {
        "schema": 1,
        "check": "dependency-audit",
        "title": "Dependency Vulnerability Check",
        "mode": "blocking",
        "status": "error",
        "summary": message,
        "problems": [message],
        "python": platform.python_version(),
    }
    return _finish(report, report_path)


def _finish(report: dict[str, Any], report_path: Path | None) -> int:
    print_report(report)
    emit_annotations(report)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {"pass": 0, "fail": 1}.get(report["status"], 2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dependency Vulnerability Check (pip-audit with the OSV database).")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTIONS, help="accepted exceptions (default: %(default)s)")
    common.add_argument("--fail-on", choices=sorted(FAIL_ON, key=FAIL_ON.__getitem__), default="high")
    common.add_argument("--report", type=Path, help="write the JSON report to this file")
    common.add_argument("--today", help=argparse.SUPPRESS)
    run = commands.add_parser("run", parents=[common], help="audit an installed environment with pip-audit")
    run.add_argument("--pip-audit", required=True, help="pip-audit executable (in its own virtual environment)")
    run.add_argument("--python", default=sys.executable, help="interpreter of the audited environment")
    classify = commands.add_parser("classify", parents=[common], help="apply the policy to a pip-audit JSON report")
    classify.add_argument("--input", type=Path, required=True)
    classify.add_argument("--osv-records", type=Path, help="JSON object of OSV records by id; no network lookup")
    commands.add_parser("validate-exceptions", parents=[common], help="validate the exceptions file")
    args = parser.parse_args(argv)

    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()
    exceptions_path = args.exceptions if args.exceptions.is_absolute() else ROOT / args.exceptions
    try:
        shown_path = exceptions_path.relative_to(ROOT).as_posix()
    except ValueError:
        shown_path = exceptions_path.as_posix()
    entries, file_problems = load_exceptions(exceptions_path)

    if args.command == "validate-exceptions":
        invalid, _, valid = match_exceptions([], entries, today)
        for problem in file_problems:
            print(f"error: {problem}")
        for item in invalid:
            print(f"error: entry {item['index']} ({item.get('id')}): {'; '.join(item['problems'])}")
        print(f"{shown_path}: {valid} valid, {len(invalid)} invalid exception entries")
        return 1 if file_problems or invalid else 0

    python_version = None
    fetch = fetch_osv_record
    tool = "pip-audit (OSV)"
    if args.command == "run":
        try:
            paths, python_version = interpreter_info(args.python)
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            return _error(f"cannot inspect the interpreter {args.python}: {exc}", args.report)
        with tempfile.TemporaryDirectory(prefix="dependency-audit-") as tmp:
            output = Path(tmp) / "pip-audit.json"
            try:
                result = run_pip_audit(args.pip_audit, paths, output)
            except OSError as exc:
                return _error(f"cannot run pip-audit: {exc}", args.report)
            if not output.exists():
                detail = (result.stderr or result.stdout).strip()[-800:]
                return _error(f"pip-audit wrote no report (exit code {result.returncode}): {detail}", args.report)
            try:
                data = json.loads(output.read_text(encoding="utf-8"))
            except ValueError as exc:
                return _error(f"the pip-audit report is not valid JSON: {exc}", args.report)
        version = subprocess.run([args.pip_audit, "--version"], capture_output=True, text=True, check=False)
        tool = f"{version.stdout.strip() or 'pip-audit'} (OSV)"
    else:
        try:
            data = json.loads(args.input.read_text(encoding="utf-8"))
            if args.osv_records is not None:
                fetch = offline_fetch(json.loads(args.osv_records.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            return _error(f"cannot read the input files: {exc}", args.report)

    report = audit(
        data,
        fetch=fetch,
        exceptions=entries,
        exceptions_problems=file_problems,
        fail_on=args.fail_on,
        today=today,
        tool=tool,
        python=python_version,
        exceptions_path=shown_path,
    )
    return _finish(report, args.report)


if __name__ == "__main__":
    sys.exit(main())
