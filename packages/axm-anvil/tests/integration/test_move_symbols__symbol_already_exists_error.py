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
