"""Integration test: mypy --strict must pass on core/callers.py.

Guards AC3: type tightening (replacing ``node: object`` by
``tree_sitter.Node``) must not introduce any mypy strict errors.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TARGET = PACKAGE_ROOT / "src" / "axm_ast" / "core" / "callers.py"


@pytest.mark.integration
def test_mypy_strict_passes_on_core_callers() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(TARGET)],
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"mypy --strict failed on {TARGET}:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
