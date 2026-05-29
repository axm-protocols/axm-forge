"""E2E test for the ``--no-include-helpers`` CLI flag on ``move``."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_SOURCE = """\
from __future__ import annotations


def _helper(x: int) -> int:
    return x + 1


def public_fn(y: int) -> int:
    return _helper(y) * 2
"""

_TARGET = """\
from __future__ import annotations
"""


@pytest.mark.e2e
def test_cli_no_include_helpers_flag(tmp_path: Path) -> None:
    """AC5: ``--no-include-helpers`` exits 0 and target lacks helper def."""
    src = tmp_path / "src_mod.py"
    tgt = tmp_path / "tgt_mod.py"
    src.write_text(_SOURCE)
    tgt.write_text(_TARGET)
    result = subprocess.run(
        [
            "axm-anvil",
            "move",
            str(src),
            str(tgt),
            "public_fn",
            "--path",
            str(tmp_path),
            "--no-include-helpers",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "def _helper" not in tgt.read_text()
