"""Integration tests for io_primitives — real-filesystem load/save."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.io_primitives import cst_load, cst_save

pytestmark = pytest.mark.integration


def test_cst_load_save_roundtrip(tmp_path: Path) -> None:
    """AC3: cst_load and cst_save preserve source byte-for-byte."""
    src = "def f():\n    return 1\n"
    path = tmp_path / "mod.py"
    path.write_text(src)
    module = cst_load(path)
    assert module is not None
    out = tmp_path / "out.py"
    cst_save(out, module)
    assert out.read_text() == src


def test_cst_load_returns_none_on_parse_error(tmp_path: Path) -> None:
    """AC3: cst_load returns None when libcst cannot parse the source."""
    path = tmp_path / "broken.py"
    path.write_text("def broken(\n")
    assert cst_load(path) is None
