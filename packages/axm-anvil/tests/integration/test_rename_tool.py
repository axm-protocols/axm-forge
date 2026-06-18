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
