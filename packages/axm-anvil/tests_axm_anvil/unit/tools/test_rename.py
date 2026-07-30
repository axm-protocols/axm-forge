"""Unit tests for :class:`axm_anvil.tools.rename.RenameTool` (no real I/O).

The tool surface is exercised through its public boundary
``RenameTool().execute``; the internal helpers and ``RenameSymbols`` /
``_discover_callers`` are never touched directly. The argument-resolution
failure branches return a ``ToolResult`` before any file is read, so they
are exercised here without touching the filesystem.
"""

from __future__ import annotations

from axm_anvil.core.callers import CallerRewrite
from axm_anvil.core.rename import RenamePlan
from axm_anvil.tools.rename import RenameTool


def test_name_is_anvil_rename() -> None:
    """AC2: the tool advertises ``anvil_rename`` for registry lookup."""
    assert RenameTool().name == "anvil_rename"


def test_execute_invalid_mapping_json_returns_failure() -> None:
    """A malformed --mapping JSON string yields ToolResult(success=False)
    before any file is read (resolution fails up front)."""
    result = RenameTool().execute(file="mod.py", mapping="{not json")

    assert result.success is False
    assert result.error is not None
    assert "invalid JSON" in result.error


def test_execute_non_object_mapping_json_returns_failure() -> None:
    """Valid JSON that is not an object (e.g. a list) is rejected."""
    result = RenameTool().execute(file="mod.py", mapping="[1, 2]")

    assert result.success is False
    assert result.error == "mapping must be a JSON object"


def test_execute_missing_old_new_returns_failure() -> None:
    """Neither --mapping nor a complete --old/--new pair yields a failure."""
    result = RenameTool().execute(file="mod.py")

    assert result.success is False
    assert result.error is not None
    assert "--old" in result.error


def test_format_text_renders_renames_and_callers() -> None:
    """The text rendering lists each rename and the caller-update count."""
    plan = RenamePlan(
        source_text_new="",
        renamed={"Old": "New"},
        callers_updated=[CallerRewrite(file="a.py", line=0, old="m", new="m")],
    )

    text = RenameTool()._format_text(plan, file="/abs/mod.py")

    assert "anvil_rename | 1 symbols | mod.py" in text
    assert "Old → New" in text
    assert "Callers Updated: 1" in text
    assert "Warnings:" not in text


def test_format_text_renders_warnings_section() -> None:
    """A plan carrying warnings renders a dedicated Warnings section."""
    plan = RenamePlan(
        source_text_new="",
        renamed={"Old": "New"},
        warnings=["symbol 'Gone' not found in module; skipped"],
    )

    text = RenameTool()._format_text(plan, file="mod.py")

    assert "Warnings:" in text
    assert "  - symbol 'Gone' not found in module; skipped" in text
