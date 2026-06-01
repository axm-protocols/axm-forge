from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import (
    SymbolNotFoundError,
)
from tests.integration._helpers import SOURCE_WITH_METHOD, _write


def test_symbol_not_found_raises(tmp_path: Path) -> None:
    # AXM-1769: the bulk path is now lenient; SymbolNotFoundError is only
    # raised under the explicit strict=True opt-in.
    src = _write(tmp_path / "src.py", "class Foo:\n    pass\n")
    tgt = _write(tmp_path / "tgt.py", "")
    with pytest.raises(SymbolNotFoundError):
        move_symbols(src, tgt, ["Nope"], dry_run=True, strict=True)


def test_move_absent_toplevel_warns_not_raises(tmp_path: Path) -> None:
    """AC5: a genuinely-absent top-level name warns clearly, no SymbolNotFoundError."""
    source = tmp_path / "source_mod.py"
    target = tmp_path / "target_mod.py"
    source.write_text(SOURCE_WITH_METHOD)
    target.write_text('"""Target module."""\n')

    try:
        plan = move_symbols(
            source,
            target,
            ["real_toplevel", "does_not_exist_anywhere"],
            workspace_root=tmp_path,
        )
    except SymbolNotFoundError as exc:  # pragma: no cover - failure path
        pytest.fail(f"move_symbols raised SymbolNotFoundError for absent name: {exc}")

    assert "real_toplevel" in plan.moved_names
    assert "does_not_exist_anywhere" not in plan.moved_names
    assert any("does_not_exist_anywhere" in w for w in plan.warnings)
