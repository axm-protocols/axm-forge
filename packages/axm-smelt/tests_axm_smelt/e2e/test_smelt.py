from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_AXM = Path(sys.executable).parent / "axm"


@pytest.mark.e2e
def test_cli_help() -> None:
    """The AXMTool-derived CLI exposes help without the retired façade."""
    result = subprocess.run(  # noqa: S603
        [str(_AXM), "smelt", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
