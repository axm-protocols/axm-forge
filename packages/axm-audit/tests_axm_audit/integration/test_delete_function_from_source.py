"""Integration tests for delete_function_from_source (real tmp_path I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import delete_function_from_source

pytestmark = pytest.mark.integration


def test_delete_function_from_source_removes_only_target(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("def a():\n    pass\n\ndef b():\n    pass\n")
    delete_function_from_source(f, "a")
    text = f.read_text()
    assert "def b(" in text
    assert "def a(" not in text
