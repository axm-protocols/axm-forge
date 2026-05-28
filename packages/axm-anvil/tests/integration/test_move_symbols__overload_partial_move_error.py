"""Split from ``test_move.py``."""

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import OverloadPartialMoveError
from tests.integration._helpers import _write


def test_overload_partial_move_raises(tmp_path: Path) -> None:
    source = (
        "from typing import overload\n\n"
        "@overload\n"
        "def process(x: int) -> int: ...\n"
        "@overload\n"
        "def process(x: str) -> str: ...\n"
        "@overload\n"
        "def process(x: bytes) -> bytes: ...\n"
        "def process(x):\n    return x\n"
    )
    src = _write(tmp_path / "src.py", source)
    tgt = _write(tmp_path / "tgt.py", "")
    with pytest.raises(OverloadPartialMoveError):
        move_symbols(src, tgt, ["process:0"], dry_run=True)
