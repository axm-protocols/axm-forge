"""Split from ``test_move.py``."""

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import SymbolAlreadyExistsError
from tests.integration._helpers import _write


def test_symbol_already_exists_raises(tmp_path: Path) -> None:
    src = _write(tmp_path / "src.py", "class Foo:\n    pass\n")
    tgt = _write(tmp_path / "tgt.py", "class Foo:\n    pass\n")
    with pytest.raises(SymbolAlreadyExistsError):
        move_symbols(src, tgt, ["Foo"], dry_run=True)


def test_move_rename_onto_existing_target_name_raises(tmp_path: Path) -> None:
    """P1-1: ``move(foo, rename={'foo': 'bar'})`` where ``bar`` already exists
    in the target must raise instead of writing two ``def bar`` into it."""
    src = _write(tmp_path / "src.py", "def foo() -> int:\n    return 1\n")
    tgt = _write(tmp_path / "tgt.py", "def bar() -> int:\n    return 2\n")
    tgt_before = tgt.read_text()

    with pytest.raises(SymbolAlreadyExistsError):
        move_symbols(src, tgt, ["foo"], rename={"foo": "bar"}, workspace_root=tmp_path)

    # Rejected before write: no second ``def bar`` was ever spliced in.
    assert tgt.read_text() == tgt_before
    assert tgt.read_text().count("def bar") == 1
