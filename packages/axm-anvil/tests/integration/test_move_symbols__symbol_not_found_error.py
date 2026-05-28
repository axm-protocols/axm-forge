from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import (
    SymbolNotFoundError,
)
from tests.integration._helpers import _write


def test_symbol_not_found_raises(tmp_path: Path) -> None:
    # AXM-1769: the bulk path is now lenient; SymbolNotFoundError is only
    # raised under the explicit strict=True opt-in.
    src = _write(tmp_path / "src.py", "class Foo:\n    pass\n")
    tgt = _write(tmp_path / "tgt.py", "")
    with pytest.raises(SymbolNotFoundError):
        move_symbols(src, tgt, ["Nope"], dry_run=True, strict=True)
