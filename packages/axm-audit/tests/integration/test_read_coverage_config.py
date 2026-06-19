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


def test_read_coverage_config_default_when_absent(tmp_path: Path) -> None:
    """AC1: a pyproject lacking the section returns the default 90.0."""
    project = _write_pyproject(
        tmp_path,
        '[project]\nname = "demo"\nversion = "0.1.0"\n',
    )

    assert read_coverage_config(project) == 90.0


def test_read_coverage_config_returns_configured(tmp_path: Path) -> None:
    """AC1: a configured ``min_coverage`` is read back as a float."""
    project = _write_pyproject(
        tmp_path,
        "[tool.axm-audit.coverage]\nmin_coverage = 75\n",
    )

    assert read_coverage_config(project) == 75.0


def test_read_coverage_config_zero(tmp_path: Path) -> None:
    """AC5: ``min_coverage = 0`` is a valid in-bounds value, returned as 0.0."""
    project = _write_pyproject(
        tmp_path,
        "[tool.axm-audit.coverage]\nmin_coverage = 0\n",
    )

    assert read_coverage_config(project) == 0.0


def test_read_coverage_config_out_of_bounds_falls_back(tmp_path: Path) -> None:
    """AC2: out-of-[0,100] or non-numeric values fall back to the default 90.0."""
    too_high = _write_pyproject(
        tmp_path,
        "[tool.axm-audit.coverage]\nmin_coverage = 150\n",
    )
    assert read_coverage_config(too_high) == 90.0

    non_numeric = _write_pyproject(
        tmp_path,
        '[tool.axm-audit.coverage]\nmin_coverage = "high"\n',
    )
    assert read_coverage_config(non_numeric) == 90.0


def test_read_coverage_config_malformed_toml(tmp_path: Path) -> None:
    """AC1: invalid TOML never raises — falls back to the default 90.0."""
    project = _write_pyproject(
        tmp_path,
        "[tool.axm-audit.coverage\nmin_coverage = = 75\n",
    )

    assert read_coverage_config(project) == 90.0
