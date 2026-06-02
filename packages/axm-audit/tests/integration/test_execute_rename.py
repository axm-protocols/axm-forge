"""Integration tests for execute_rename (real fs + git + libcst + anvil)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import execute_rename

pytestmark = pytest.mark.integration


def _op(
    kind: str,
    source: Path,
    target: Path | list[Path],
    *,
    split_map: dict[str, list[str]] | None = None,
) -> FileOp:
    return FileOp(
        kind=kind,
        source=source,
        target=target,
        rationale="r",
        source_rule="X",
        split_map=split_map,
    )


def test_execute_rename_git_moves_to_canonical_name(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """RENAME git-moves the source to its canonical name when target is free."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_old.py": "def test_thing():\n    assert True\n",
        }
    )
    src = pkg / "tests/integration/test_old.py"
    tgt = pkg / "tests/integration/test_new.py"

    warnings = execute_rename(_op("rename", src, tgt), pkg)

    assert warnings == []
    assert not src.exists()
    assert "def test_thing():" in tgt.read_text()


def test_execute_rename_reroutes_when_target_exists(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """RENAME re-routes through _safe_move_units when the canonical name is taken."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_old.py": "def test_from_old():\n    assert True\n",
            "tests/integration/test_new.py": "def test_existing():\n    assert True\n",
        }
    )
    src = pkg / "tests/integration/test_old.py"
    tgt = pkg / "tests/integration/test_new.py"

    warnings = execute_rename(_op("rename", src, tgt), pkg)

    assert warnings == [
        "rename: target test_new.py already exists; "
        "re-routing test_old.py through _safe_move_units"
    ]
    assert not src.exists()
    body = tgt.read_text()
    assert "def test_existing():" in body
    assert "def test_from_old():" in body
