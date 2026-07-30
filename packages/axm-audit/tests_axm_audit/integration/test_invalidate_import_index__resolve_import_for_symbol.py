"""Integration tests for invalidate_import_index + resolve_import_for_symbol."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import (
    invalidate_import_index,
    resolve_import_for_symbol,
)

pytestmark = pytest.mark.integration


def test_resolve_import_for_symbol_finds_top_level_def(tmp_path: Path) -> None:
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("def my_function():\n    return 1\n")
    invalidate_import_index(tmp_path)
    result = resolve_import_for_symbol(tmp_path, "my_function")
    assert result is not None
    stmt, enclosing = result
    import ast

    assert isinstance(stmt, ast.ImportFrom)
    assert stmt.module == "mypkg.mod"
    assert enclosing is None


def test_resolve_import_for_symbol_unknown_returns_none(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("x = 1\n")
    invalidate_import_index(tmp_path)
    assert resolve_import_for_symbol(tmp_path, "no_such_symbol") is None
