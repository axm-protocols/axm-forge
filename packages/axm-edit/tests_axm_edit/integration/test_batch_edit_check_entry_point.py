"""Integration tests for the ``batch_edit_check`` axm.tools entry point.

Reads the installed distribution metadata (real I/O), not the source tree.
"""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest

EXPECTED_NAME = "batch_edit_check"
EXPECTED_VALUE = "axm_edit.tools.batch_edit_check:BatchEditCheckTool"


@pytest.mark.integration
def test_batch_edit_check_is_declared_under_axm_tools() -> None:
    """AC1: the ``axm.tools`` group exposes ``batch_edit_check``."""
    declared = list(entry_points(group="axm.tools"))
    names = sorted(entry.name for entry in declared)

    assert EXPECTED_NAME in names, names


@pytest.mark.integration
def test_batch_edit_check_entry_point_points_at_the_tool_class() -> None:
    """AC1: the entry point value targets ``BatchEditCheckTool``."""
    declared = list(entry_points(group="axm.tools"))
    matching = [entry for entry in declared if entry.name == EXPECTED_NAME]

    assert matching, sorted(entry.name for entry in declared)
    assert matching[0].value == EXPECTED_VALUE
