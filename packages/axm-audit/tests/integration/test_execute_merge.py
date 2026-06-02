"""Integration tests for execute_merge (real fs + git + libcst + anvil)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import execute_merge

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


def test_execute_merge_moves_units_and_deletes_empty_source(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """MERGE relocates the source's units into target then deletes the source."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_src.py": "def test_from_src():\n    assert True\n",
            "tests/integration/test_tgt.py": "def test_in_tgt():\n    assert True\n",
        }
    )
    src = pkg / "tests/integration/test_src.py"
    tgt = pkg / "tests/integration/test_tgt.py"

    execute_merge(_op("merge", src, tgt), pkg)

    assert not src.exists()
    body = tgt.read_text()
    assert "def test_in_tgt():" in body
    assert "def test_from_src():" in body


def test_execute_merge_skipped_when_source_has_no_units(
    make_test_pkg: Callable[[dict[str, str]], Path],
) -> None:
    """MERGE skips with a no-movable-units message when the source is empty."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_src.py": '"""docstring only."""\n',
            "tests/integration/test_tgt.py": "def test_in_tgt():\n    assert True\n",
        }
    )
    src = pkg / "tests/integration/test_src.py"
    tgt = pkg / "tests/integration/test_tgt.py"

    warnings = execute_merge(_op("merge", src, tgt), pkg)

    assert warnings == [f"merge skipped: {src} has no top-level movable units"]
    assert src.exists()
