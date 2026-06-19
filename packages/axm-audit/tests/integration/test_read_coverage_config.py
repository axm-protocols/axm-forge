"""Integration tests for reading the coverage config from a real pyproject file."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.coverage import read_coverage_config

pytestmark = pytest.mark.integration


def _write_pyproject(tmp_path: Path, body: str) -> Path:
    """Write a pyproject.toml with ``body`` into ``tmp_path`` and return it."""
    (tmp_path / "pyproject.toml").write_text(body, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        pytest.param(
            '[project]\nname = "demo"\nversion = "0.1.0"\n',
            90.0,
            id="default_when_absent",
        ),
        pytest.param(
            "[tool.axm-audit.coverage]\nmin_coverage = 75\n", 75.0, id="configured"
        ),
        pytest.param(
            "[tool.axm-audit.coverage]\nmin_coverage = 0\n", 0.0, id="zero_in_bounds"
        ),
        pytest.param(
            "[tool.axm-audit.coverage]\nmin_coverage = 150\n",
            90.0,
            id="too_high_falls_back",
        ),
        pytest.param(
            '[tool.axm-audit.coverage]\nmin_coverage = "high"\n',
            90.0,
            id="non_numeric_falls_back",
        ),
        pytest.param(
            "[tool.axm-audit.coverage\nmin_coverage = = 75\n",
            90.0,
            id="malformed_toml_falls_back",
        ),
    ],
)
def test_read_coverage_config(tmp_path: Path, body: str, expected: float) -> None:
    """read_coverage_config reads min_coverage, defaulting to 90.0 on any problem.

    Covers: absent section, in-bounds values (incl. 0), out-of-bounds and
    non-numeric fall-backs, and malformed TOML (never raises).
    """
    project = _write_pyproject(tmp_path, body)

    assert read_coverage_config(project) == expected
