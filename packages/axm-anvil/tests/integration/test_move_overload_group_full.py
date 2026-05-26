from __future__ import annotations

from pathlib import Path

import libcst as cst
import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


def test_move_overload_group_full(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from typing import overload\n\n"
        "@overload\n"
        "def f(x: int) -> int: ...\n"
        "@overload\n"
        "def f(x: str) -> str: ...\n"
        "def f(x):\n    return x\n"
    )
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(src, tgt, ["f"], dry_run=False)
    target_text = tgt.read_text()

    module = cst.parse_module(target_text)
    func_defs = [
        n for n in module.body if isinstance(n, cst.FunctionDef) and n.name.value == "f"
    ]
    assert len(func_defs) == 3
