from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.tools.rename import RenameTool

pytestmark = pytest.mark.integration


def test_missing_symbol_returns_failure(tmp_path: Path) -> None:
    """AC5: an absent symbol yields ToolResult(success=False), no raw exception."""
    src = tmp_path / "mod.py"
    src.write_text("def kept() -> int:\n    return 1\n")

    result = RenameTool().execute(
        path=str(tmp_path),
        file="mod.py",
        old="DoesNotExist",
        new="NewName",
        strict=True,
    )

    assert result.success is False
    assert result.error


def test_result_data_shape(tmp_path: Path) -> None:
    """AC4: dry_run ToolResult.data exposes the same shape as anvil_move."""
    src = tmp_path / "mod.py"
    src.write_text("def old_fn() -> int:\n    return old_fn.__name__ and 1\n")

    result = RenameTool().execute(
        path=str(tmp_path),
        file="mod.py",
        old="old_fn",
        new="new_fn",
        dry_run=True,
    )

    assert result.success is True
    assert result.data is not None
    for key in ("renamed", "callers_updated", "warnings", "files_modified"):
        assert key in result.data


def test_mapping_json_object_renders_text(tmp_path: Path) -> None:
    """A --mapping JSON object drives the batch rename and the text summary."""
    src = tmp_path / "mod.py"
    src.write_text("def old_fn() -> int:\n    return old_fn.__name__ and 1\n")

    result = RenameTool().execute(
        path=str(tmp_path),
        file="mod.py",
        mapping='{"old_fn": "new_fn"}',
        dry_run=True,
    )

    assert result.success is True
    assert result.data is not None
    assert {"old": "old_fn", "new": "new_fn"} in result.data["renamed"]
    assert result.text is not None
    assert "old_fn → new_fn" in result.text


def test_warning_rendered_in_text_for_absent_symbol(tmp_path: Path) -> None:
    """A non-strict rename mixing a present and an absent symbol records the
    skip warning in the rendered text (Warnings section)."""
    src = tmp_path / "mod.py"
    src.write_text("def present() -> int:\n    return present.__name__ and 1\n")

    result = RenameTool().execute(
        path=str(tmp_path),
        file="mod.py",
        mapping='{"present": "kept", "absent": "ghost"}',
        dry_run=True,
    )

    assert result.success is True
    assert result.text is not None
    assert "Warnings:" in result.text
    assert "absent" in result.text


def test_rename_to_keyword_surfaces_validation_failure(tmp_path: Path) -> None:
    """A rename producing unparseable code (a Python keyword) is surfaced as a
    ToolResult failure (MoveValidationError arm of _exception_to_result)."""
    src = tmp_path / "mod.py"
    src.write_text("def foo() -> int:\n    return 1\n")

    result = RenameTool().execute(
        path=str(tmp_path),
        file="mod.py",
        old="foo",
        new="class",
    )

    assert result.success is False
    assert result.error is not None
    assert "parse" in result.error


def test_missing_source_file_surfaces_failure(tmp_path: Path) -> None:
    """A non-existent source file raises an OSError inside rename_symbols,
    surfaced via the generic arm of _exception_to_result."""
    result = RenameTool().execute(
        path=str(tmp_path),
        file="does_not_exist.py",
        old="foo",
        new="bar",
    )

    assert result.success is False
    assert result.error
