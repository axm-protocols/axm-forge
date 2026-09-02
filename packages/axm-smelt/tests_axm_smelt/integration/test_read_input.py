"""Filesystem contract for the retired CLI façade."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.integration
def test_retired_cli_sources_are_absent() -> None:
    """The two retired façade source modules are absent from the package tree."""
    package_root = Path(__file__).parents[2]

    assert not (package_root / "src/axm_smelt/cli.py").exists()
    assert not (package_root / "src/axm_smelt/__main__.py").exists()
