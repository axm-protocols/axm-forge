"""Integration tests: impact_text module is real, not a sys.modules shim."""

from __future__ import annotations

from pathlib import Path

import pytest

import axm_ast

pytestmark = pytest.mark.integration


def test_no_sys_modules_shim_remains() -> None:
    """AC2: tools/impact.py no longer injects impact_text via sys.modules."""
    impact_path = Path(axm_ast.__file__).parent / "tools" / "impact.py"
    source = impact_path.read_text(encoding="utf-8")

    assert 'sys.modules["axm_ast.tools.impact_text"]' not in source
    assert "sys.modules['axm_ast.tools.impact_text']" not in source
