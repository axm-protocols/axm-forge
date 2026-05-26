from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import (
    OverloadPartialMoveError,
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
)


def _write(path: Path, text: str) -> Path:
    path.write_text(text)
    return path


def test_symbol_not_found_raises(tmp_path: Path) -> None:
    src = _write(tmp_path / "src.py", "class Foo:\n    pass\n")
    tgt = _write(tmp_path / "tgt.py", "")
    with pytest.raises(SymbolNotFoundError):
        move_symbols(src, tgt, ["Nope"], dry_run=True)


def test_symbol_already_exists_raises(tmp_path: Path) -> None:
    src = _write(tmp_path / "src.py", "class Foo:\n    pass\n")
    tgt = _write(tmp_path / "tgt.py", "class Foo:\n    pass\n")
    with pytest.raises(SymbolAlreadyExistsError):
        move_symbols(src, tgt, ["Foo"], dry_run=True)


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


def test_dry_run_no_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}

    def fake_batch_edit(*args: object, **kwargs: object) -> None:
        called["count"] += 1

    monkeypatch.setattr(
        "axm_anvil.core.move.batch_edit", fake_batch_edit, raising=False
    )
    src = _write(tmp_path / "src.py", "class Foo:\n    pass\n")
    tgt = _write(tmp_path / "tgt.py", "")
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert called["count"] == 0
    assert plan is not None
    assert "Foo" in plan.moved_names
