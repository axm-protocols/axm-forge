"""Integration tests for the `near_threshold` advisory opt-in (AC1)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"


@pytest.mark.integration
def test_pyproject_enables_near_threshold_advisory() -> None:
    """AC1: `[tool.axm-audit.complexity] near_threshold = true` is declared.

    The package is the pilot for the warn-only `near_threshold` advisory, so
    its own `pyproject.toml` must carry the explicit opt-in.
    """
    with PYPROJECT.open("rb") as handle:
        data = tomllib.load(handle)

    complexity = data["tool"]["axm-audit"]["complexity"]

    assert complexity["near_threshold"] is True
