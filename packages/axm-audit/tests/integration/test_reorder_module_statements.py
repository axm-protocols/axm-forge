"""Integration tests for reorder_module_statements (real tmp_path I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import reorder_module_statements

pytestmark = pytest.mark.integration


def test_reorder_module_statements_moves_def_before_use(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text(
        "import pytest\n\n"
        "_skip = pytest.mark.skipif(_tools_available())\n\n"
        "def _tools_available():\n"
        "    return False\n"
    )
    reorder_module_statements(f)
    text = f.read_text()
    # The definition of _tools_available must precede the assignment that uses it.
    assert text.index("def _tools_available") < text.index("_skip = pytest")


def test_reorder_module_statements_already_ordered_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    original = (
        "import pytest\n\n"
        "def _tools_available():\n"
        "    return False\n\n"
        "_skip = pytest.mark.skipif(_tools_available())\n"
    )
    f.write_text(original)
    reorder_module_statements(f)
    assert f.read_text() == original


def test_reorder_module_statements_invalid_syntax_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    # libcst parses lenient enough but ast.parse fails -> bail, file untouched.
    original = "def (:\n"
    f.write_text(original)
    reorder_module_statements(f)
    assert f.read_text() == original
