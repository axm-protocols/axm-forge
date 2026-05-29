from __future__ import annotations

from pathlib import Path

from axm_anvil.tools.move import MoveTool


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
