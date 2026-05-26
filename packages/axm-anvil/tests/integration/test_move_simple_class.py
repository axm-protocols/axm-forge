from __future__ import annotations

import shutil
from pathlib import Path

import libcst as cst
import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    shutil.copy(FIXTURES / "source.py", src)
    shutil.copy(FIXTURES / "target.py", tgt)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")
    return src, tgt


def test_move_simple_class(tmp_path: Path) -> None:
    src, tgt = _setup(tmp_path)
    plan = move_symbols(
        src, tgt, ["TestFilesystemInvalidation", "TestEdgeCases"], dry_run=False
    )
    assert "TestFilesystemInvalidation" in plan.moved_names
    assert "TestEdgeCases" in plan.moved_names

    target_text = tgt.read_text()
    assert "class TestFilesystemInvalidation" in target_text
    assert "class TestEdgeCases" in target_text
    cst.parse_module(target_text)

    source_text = src.read_text()
    assert "class TestFilesystemInvalidation" not in source_text
    assert "class TestEdgeCases" not in source_text
