from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_smelt.core.pipeline import check as _check

pytestmark = pytest.mark.e2e

SAMPLE = '{"name": "value", "items": [1, 2, 3], "nested": {"a": 1, "b": 2}}'


def _run_check(tmp_path: Path) -> str:
    src = tmp_path / "input.json"
    src.write_text(SAMPLE, encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "axm-smelt", "check", "--file", str(src)],  # noqa: S607
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_check_output_includes_savings_line(tmp_path: Path) -> None:
    """AC1/AC2: check output carries the cumulative savings_pct from the report."""
    stdout = _run_check(tmp_path)
    report = _check(SAMPLE)
    expected = f"Savings: {report.savings_pct:.1f}%"
    assert expected in stdout


def test_check_existing_lines_remain(tmp_path: Path) -> None:
    """AC3: Format/Tokens/Strategies lines stay present."""
    stdout = _run_check(tmp_path)
    assert "Format:" in stdout
    assert "Tokens:" in stdout
    assert "Strategies applied:" in stdout
