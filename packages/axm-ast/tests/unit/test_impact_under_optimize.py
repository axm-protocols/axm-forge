"""Integration test: ImpactTool unit tests pass under ``python -O``.

AC4: with ``-O`` Python strips ``assert`` statements. If any production
code path in ``tools.impact`` still relied on an ``assert`` for type
narrowing or guard, the unit suite would fail under ``-O``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_impact_tool_works_under_python_optimize() -> None:
    """Run ``tests/unit/tools/test_impact.py`` with ``python -O``."""
    proc = subprocess.run(
        [
            sys.executable,
            "-O",
            "-m",
            "pytest",
            "tests/unit/tools/test_impact.py",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-W",
            "ignore::pytest.PytestConfigWarning",
        ],
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, (
        f"pytest under -O failed (exit={proc.returncode}).\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
