"""End-to-end tests for removed standalone package entry points."""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.e2e
def test_cli_module_cannot_be_imported() -> None:
    """AC1: the removed CLI façade is not importable in a child interpreter."""
    result = subprocess.run(
        [sys.executable, "-c", "import axm_smelt.cli"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode != 0
    assert "No module named 'axm_smelt.cli'" in result.stderr


@pytest.mark.e2e
def test_package_cannot_be_executed_with_dash_m() -> None:
    """AC2: package execution fails when the main module has been removed."""
    result = subprocess.run(
        [sys.executable, "-m", "axm_smelt"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode != 0
    assert "No module named axm_smelt.__main__" in result.stderr
