"""Phase 3.5 regression tests: alert conditions are parsed, never passed to eval().

Bandit B307 (docs/security/PHASE3_5_SECURITY_HARDENING.md).

Vulnerability: AlertManager._evaluate_condition put str(value) of every metric
into the condition text and passed the result to eval(). A metric value or a
rule condition that contained Python code was executed.

Expected: a small grammar (metric names, 'threshold', numbers, comparison
operators, and/or) is evaluated on a checked syntax tree. Anything else is
refused and never executed.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ragbot.monitoring.alert_manager import AlertManager, AlertRule

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "ragbot" / "monitoring" / "alert_manager.py"


@pytest.mark.parametrize(
    ("condition", "metrics", "expected"),
    [
        ("cpu_usage > threshold", {"cpu_usage": 90.0}, True),
        ("cpu_usage > threshold", {"cpu_usage": 80.0}, False),
        ("cpu_usage >= threshold", {"cpu_usage": 80.0}, True),
        ("memory_usage < threshold", {"memory_usage": 12}, True),
        ("memory_usage <= threshold", {"memory_usage": 80}, True),
        ("error_rate == threshold", {"error_rate": 80}, True),
        ("error_rate != threshold", {"error_rate": 80}, False),
        ("0 < response_time < threshold", {"response_time": 5}, True),
        ("cpu_usage > threshold and disk_usage > 50", {"cpu_usage": 90, "disk_usage": 60}, True),
        ("cpu_usage > threshold and disk_usage > 50", {"cpu_usage": 90, "disk_usage": 40}, False),
        ("cpu_usage > threshold or disk_usage > 50", {"cpu_usage": 10, "disk_usage": 60}, True),
        ("delta > -5", {"delta": -1}, True),
        ("cpu_usage > 79.5", {"cpu_usage": np.float64(80.0)}, True),
        ("cpu_usage > threshold", {"cpu_usage": np.int64(81)}, True),
    ],
)
async def test_supported_conditions_are_evaluated(condition: str, metrics: dict[str, Any], expected: bool) -> None:
    assert await AlertManager()._evaluate_condition(condition, 80.0, metrics) is expected


async def test_a_condition_with_a_missing_metric_does_not_fire() -> None:
    assert await AlertManager()._evaluate_condition("cpu_usage > threshold", 80.0, {}) is False


@pytest.mark.parametrize("value", ["90", True, None, [90]], ids=["string", "bool", "none", "list"])
async def test_a_metric_value_that_is_not_a_number_does_not_fire(value: Any) -> None:
    manager = AlertManager()
    assert await manager._evaluate_condition("cpu_usage > threshold", 80.0, {"cpu_usage": value}) is False


UNSUPPORTED = [
    "__import__('os').system('true')",
    "cpu_usage > threshold + 1",
    "cpu_usage.real > 1",
    "metrics['cpu_usage'] > 1",
    "len(cpu_usage) > 1",
    "'a' < 'b'",
    "cpu_usage",
    "True",
    "not cpu_usage > 1",
    "cpu_usage is None",
    "cpu_usage in [1, 2]",
    "(cpu_usage if cpu_usage else 0) > 1",
    "lambda: 1",
    "(cpu_usage := 1) > 0",
    "cpu_usage > True",
    "-cpu_usage > 1",
    "",
    "   ",
    "cpu_usage > " + "1" * 300,
]


@pytest.mark.parametrize("condition", UNSUPPORTED)
def test_unsupported_conditions_are_refused(condition: str) -> None:
    from ragbot.monitoring.alert_manager import UnsupportedConditionError, parse_condition

    with pytest.raises(UnsupportedConditionError):
        parse_condition(condition)


async def test_a_metric_value_is_never_executed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    payload = "__import__('pathlib').Path('p35-metric-marker').touch() or 0"
    fired = await AlertManager()._evaluate_condition("cpu_usage > threshold", 80.0, {"cpu_usage": payload})
    assert not (tmp_path / "p35-metric-marker").exists()
    assert fired is False


async def test_a_rule_condition_is_never_executed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    manager = AlertManager()
    manager.alert_rules = {
        "evil": AlertRule("Evil", "__import__('pathlib').Path('p35-rule-marker').touch() or 1 > 0", 0.0, "critical")
    }
    await manager.evaluate_metrics({"cpu_usage": 1.0})
    assert not (tmp_path / "p35-rule-marker").exists()
    assert manager.alert_history == []


async def test_add_alert_rule_refuses_an_unsupported_condition() -> None:
    from ragbot.monitoring.alert_manager import UnsupportedConditionError

    manager = AlertManager()
    with pytest.raises(UnsupportedConditionError):
        await manager.add_alert_rule("evil", AlertRule("Evil", "__import__('os').getcwd() != ''", 0.0, "critical"))
    assert "evil" not in manager.alert_rules


async def test_the_default_rules_still_fire() -> None:
    manager = AlertManager()
    await manager.evaluate_metrics(
        {"cpu_usage": 95.0, "memory_usage": 10.0, "disk_usage": 10.0, "response_time": 0.1, "error_rate": 0.0}
    )
    assert [alert["rule_id"] for alert in manager.alert_history] == ["high_cpu"]


def test_the_module_does_not_call_eval_or_exec() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not called & {"eval", "exec", "compile"}
