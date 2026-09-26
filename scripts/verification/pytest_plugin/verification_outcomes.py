"""Pytest plugin that records the collected tests and the outcome of each test.

The Verification Pipeline loads it with ``-p verification_outcomes`` (see
``scripts/verification/run_suite.py``). When the environment variable
``VERIFICATION_PYTEST_REPORT`` names a file, the plugin writes a JSON report
to that file at the end of the session. Without the variable it does nothing.

Report fields:

- ``collected``: node ids selected to run, in collection order
- ``deselected``: node ids removed by ``-k``, ``-m`` or ``--deselect``
- ``outcomes``: node id to ``passed``, ``failed``, ``error``, ``skipped``,
  ``xfailed`` or ``xpassed``
- ``skip_reasons`` and ``failures``: a short message per node id
- ``collection_problems``: test files that could not be imported, or that
  were skipped as a whole (for example with ``pytest.importorskip``)
"""

from __future__ import annotations

import json
import os
import platform
import time
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

REPORT_ENV = "VERIFICATION_PYTEST_REPORT"
PLUGIN_NAME = "verification-outcome-recorder"
MAX_MESSAGE = 500
_RANK = {"passed": 0, "xpassed": 1, "xfailed": 2, "skipped": 3, "error": 4, "failed": 5}


def _short(value: object) -> str:
    text = str(value or "").strip()
    if len(text) > MAX_MESSAGE:
        return text[: MAX_MESSAGE - 3] + "..."
    return text


def _skip_reason(report: Any) -> str:
    longrepr = getattr(report, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return _short(longrepr[2])
    return _short(getattr(report, "longreprtext", "") or longrepr)


def _failure_message(report: Any) -> str:
    crash = getattr(getattr(report, "longrepr", None), "reprcrash", None)
    message = getattr(crash, "message", None)
    if message:
        return _short(message)
    return _short(getattr(report, "longreprtext", ""))


class OutcomeRecorder:
    """Collect the data for the JSON report of one pytest session."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.started = time.monotonic()
        self.collected: list[str] = []
        self.deselected: list[str] = []
        self.outcomes: dict[str, str] = {}
        self.skip_reasons: dict[str, str] = {}
        self.failures: dict[str, str] = {}
        self.collection_problems: list[dict[str, str]] = []

    def _record(self, nodeid: str, outcome: str) -> None:
        current = self.outcomes.get(nodeid)
        if current is None or _RANK[outcome] > _RANK[current]:
            self.outcomes[nodeid] = outcome

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self.collection_problems.append(
                {"nodeid": report.nodeid, "outcome": "error", "detail": _short(report.longreprtext)}
            )
        elif report.skipped:
            self.collection_problems.append(
                {"nodeid": report.nodeid, "outcome": "skipped", "detail": _skip_reason(report)}
            )

    def pytest_deselected(self, items: list[pytest.Item]) -> None:
        self.deselected.extend(item.nodeid for item in items)

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        nodeid = report.nodeid
        xfail = hasattr(report, "wasxfail")
        if report.when == "call" and report.passed:
            self._record(nodeid, "xpassed" if xfail else "passed")
        elif report.skipped:
            self._record(nodeid, "xfailed" if xfail else "skipped")
            reason = f"xfail: {report.wasxfail}" if xfail else _skip_reason(report)
            self.skip_reasons.setdefault(nodeid, _short(reason))
        elif report.failed and report.when == "call":
            self._record(nodeid, "failed")
            self.failures[nodeid] = _failure_message(report)
        elif report.failed:
            self._record(nodeid, "error")
            self.failures.setdefault(nodeid, f"error in {report.when}: {_failure_message(report)}")

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        data = {
            "schema": 1,
            "python": platform.python_version(),
            "exit_status": int(exitstatus),
            "duration_seconds": round(time.monotonic() - self.started, 2),
            "collected": self.collected,
            "deselected": sorted(self.deselected),
            "outcomes": self.outcomes,
            "counts": dict(Counter(self.outcomes.values())),
            "skip_reasons": self.skip_reasons,
            "failures": self.failures,
            "collection_problems": self.collection_problems,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def pytest_configure(config: pytest.Config) -> None:
    target = os.environ.get(REPORT_ENV)
    if target and not config.pluginmanager.has_plugin(PLUGIN_NAME):
        config.pluginmanager.register(OutcomeRecorder(Path(target)), PLUGIN_NAME)
