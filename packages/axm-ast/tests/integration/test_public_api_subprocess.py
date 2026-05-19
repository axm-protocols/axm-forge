"""Regression tests for axm_ast top-level public API (__init__.py surface).

Not a strict mirror of __init__.py (which is exempt); these are scenario-style
guards for facade resolution and import-side-effect safety.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

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
