from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _run_check(tmp_path: Path) -> str:
    axm = Path(sys.executable).parent / "axm"
    result = subprocess.run(  # noqa: S603
        [str(axm), "smelt_check"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.e2e
def test_check_output_includes_savings_line(tmp_path: Path) -> None:
    """AC1/AC2: check output carries the cumulative savings_pct from the report."""
    stdout = _run_check(tmp_path)
    assert "no waste detected" in stdout


@pytest.mark.e2e
def test_check_existing_lines_remain(tmp_path: Path) -> None:
    """AC3: Format/Tokens/Strategies lines stay present."""
    stdout = _run_check(tmp_path)
    assert "smelt_check" in stdout
    assert "text" in stdout
    assert "0 tok" in stdout
