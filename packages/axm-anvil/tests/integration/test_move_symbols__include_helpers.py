"""Integration test for ``include_helpers=False`` against real files."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

_SOURCE = """\
from __future__ import annotations


def _helper(x: int) -> int:
    return x + 1


def public_fn(y: int) -> int:
    return _helper(y) * 2
"""

_TARGET = """\
from __future__ import annotations
"""


@pytest.mark.integration
def test_include_helpers_false_real_files(tmp_path: Path) -> None:
    """AC2: written target file does not define the skipped helper."""
    src = tmp_path / "src_mod.py"
    tgt = tmp_path / "tgt_mod.py"
    src.write_text(_SOURCE)
    tgt.write_text(_TARGET)
    move_symbols(
        src,
        tgt,
        ["public_fn"],
        workspace_root=tmp_path,
        include_helpers=False,
    )
    written = tgt.read_text()
    assert "def _helper" not in written
    assert "def public_fn" in written
