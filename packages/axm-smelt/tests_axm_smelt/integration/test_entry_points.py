"""Integration tests for the package's declared entry points."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


@pytest.mark.integration
def test_legacy_command_entry_points_are_absent() -> None:
    """AC3: metadata retains AXMTools but no standalone command declarations."""
    package_root = Path(__file__).parents[2]
    metadata_path = package_root / "pyproject.toml"
    metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
    project = metadata["project"]
    entry_points = project.get("entry-points", {})

    assert "axm-smelt" not in project.get("scripts", {})
    assert "axm.commands" not in entry_points
    assert set(entry_points["axm.tools"]) == {"smelt", "smelt_check", "smelt_count"}
