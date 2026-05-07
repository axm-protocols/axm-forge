"""Integration tests: impact_text module is real, not a sys.modules shim."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import axm_ast

pytestmark = pytest.mark.integration


def test_impact_text_resolves_in_fresh_interpreter() -> None:
    """AC4: importing impact_text works without first importing tools.impact."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from axm_ast.tools.impact_text import render_impact_text; print('ok')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_no_sys_modules_shim_remains() -> None:
    """AC2: tools/impact.py no longer injects impact_text via sys.modules."""
    impact_path = Path(axm_ast.__file__).parent / "tools" / "impact.py"
    source = impact_path.read_text(encoding="utf-8")

    assert 'sys.modules["axm_ast.tools.impact_text"]' not in source
    assert "sys.modules['axm_ast.tools.impact_text']" not in source
