from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.tools.move import MoveTool

pytestmark = pytest.mark.integration


def test_execute_rename_moves_and_renames(tmp_path: Path) -> None:
    """AC1, AC5: rename moves the symbol to the target under its new name and
    rewrites callers to reference the new name."""
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.0.0"\n'
    )
    old = pkg / "old.py"
    old.write_text("def OldName():\n    return 1\n")
    new = pkg / "new.py"
    new.write_text("")
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import OldName\n\nOldName()\n")

    result = MoveTool().execute(
        path=str(tmp_path),
        symbols="OldName",
        from_file=str(old),
        to_file=str(new),
        rename='{"OldName":"NewName"}',
    )

    assert result.success is True, result.error
    assert "def NewName" in new.read_text()
    assert "OldName" not in old.read_text()
    assert "NewName" in caller.read_text()


def test_insert_after_places_block_after_anchor(tmp_path: Path) -> None:
    """AC1: the moved block is inserted right after the named anchor and before
    the symbol that originally followed the anchor in the target module."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n\n\ndef After():\n    return 2\n")

    move_symbols(src, tgt, ["Moved"], insert_after="Anchor")

    text = tgt.read_text()
    assert text.index("def Anchor") < text.index("def Moved") < text.index("def After")
