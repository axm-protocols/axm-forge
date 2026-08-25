"""Discovery of the ``file_bytes`` tool through installed package metadata."""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest

pytestmark = pytest.mark.integration


def test_file_bytes_entry_point_is_declared() -> None:
    """AC1: an ``axm.tools`` entry point named ``file_bytes`` is installed."""
    names = {ep.name for ep in entry_points(group="axm.tools")}

    assert "file_bytes" in names, (
        "no `file_bytes` entry point declared under the `axm.tools` group"
    )


def test_file_bytes_entry_point_loads_the_tool_class() -> None:
    """AC1: loading the entry point returns ``FileBytesTool``."""
    selected = [ep for ep in entry_points(group="axm.tools") if ep.name == "file_bytes"]
    assert selected, "no `file_bytes` entry point to load"

    loaded = selected[0].load()

    assert loaded.__name__ == "FileBytesTool"
    assert loaded.__module__ == "axm_edit.tools.file_bytes"
