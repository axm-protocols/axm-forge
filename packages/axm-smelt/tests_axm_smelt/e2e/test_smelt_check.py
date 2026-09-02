from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import tiktoken


def _run_check(tmp_path: Path, text: str | None = None) -> str:
    axm = Path(sys.executable).parent / "axm"
    result = subprocess.run(  # noqa: S603
        [str(axm), "smelt_check"],
        capture_output=True,
        text=True,
        input=text,
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


@pytest.mark.e2e
def test_check_reads_redirected_text(tmp_path: Path) -> None:
    """AC7: smelt_check reports the exact token count redirected on stdin."""
    text = "alpha beta gamma delta epsilon"
    stdout = _run_check(tmp_path, text)
    expected = len(tiktoken.get_encoding("o200k_base").encode(text))

    match = re.search(r"\|\s*(\d+)\s+tok", stdout)
    assert match is not None, stdout
    assert expected > 0
    assert int(match.group(1)) == expected
