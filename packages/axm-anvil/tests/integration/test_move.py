"""Integration tests for the move CLI/tool rename and insert-after paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.tools.move import MoveTool

pytestmark = pytest.mark.integration


def _write_pair(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Foo():\n    return 1\n")
    tgt.write_text("")
    return src, tgt


def test_execute_rename_invalid_json_returns_error(tmp_path: Path) -> None:
    """AC2: invalid JSON in rename returns success=False without raising."""
    src, tgt = _write_pair(tmp_path)
    result = MoveTool().execute(
        path=str(tmp_path),
        symbols="Foo",
        from_file=str(src),
        to_file=str(tgt),
        rename="{bad",
    )
    assert result.success is False
    assert "json" in (result.error or "").lower()


def test_execute_rename_with_reexport_errors(tmp_path: Path) -> None:
    """AC3: rename combined with reexport surfaces the ValueError as a result."""
    src, tgt = _write_pair(tmp_path)
    result = MoveTool().execute(
        path=str(tmp_path),
        symbols="Foo",
        from_file=str(src),
        to_file=str(tgt),
        rename='{"Foo":"Bar"}',
        reexport=True,
    )
    assert result.success is False
    assert "incompatible" in (result.error or "").lower()


def test_insert_after_none_appends_at_end(tmp_path: Path) -> None:
    """AC2: insert_after=None preserves the historical end-append contract."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n\n\ndef Tail():\n    return 2\n")

    plan = move_symbols(src, tgt, ["Moved"], dry_run=True, insert_after=None)

    text = plan.target_text_new
    assert text.index("def Moved") > text.index("def Anchor")
    assert text.index("def Moved") > text.index("def Tail")


def test_insert_after_absent_warns_and_appends(tmp_path: Path) -> None:
    """AC3: an absent insert_after anchor appends at end and adds a warning."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n")

    plan = move_symbols(src, tgt, ["Moved"], dry_run=True, insert_after="NoSuch")

    text = plan.target_text_new
    assert text.index("def Moved") > text.index("def Anchor")
    assert any("NoSuch" in w for w in plan.warnings)
