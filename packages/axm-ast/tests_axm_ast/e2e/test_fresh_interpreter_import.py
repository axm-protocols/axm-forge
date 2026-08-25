"""End-to-end tests for impact_text public-API import (subprocess)."""

from __future__ import annotations

import subprocess
import sys


class TestImpactTextFreshInterpreter:
    """Public-API regression: fresh-interpreter import path."""

    def test_impact_text_resolves_in_fresh_interpreter(self) -> None:
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
