"""Fixtures for the tests of the Verification Pipeline tools in scripts/verification."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "verification"


def _load(name: str) -> ModuleType:
    module_name = f"verification_tools_{name}"
    module = sys.modules.get(module_name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load scripts/verification/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Root directory of the repository."""
    return ROOT


@pytest.fixture(scope="session")
def verification_script() -> Callable[[str], ModuleType]:
    """Import a module of scripts/verification by its file name without '.py'."""
    return _load


@pytest.fixture
def clean_coverage_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a nested pytest run from writing coverage data of the outer run."""
    for name in [name for name in list(__import__("os").environ) if name.startswith("COV_CORE_")]:
        monkeypatch.delenv(name)
