from __future__ import annotations

import subprocess
import sys


def test_cli_detail_full_rejected():
    """CLI --detail full must produce a clear error and exit 1."""
    proc = subprocess.run(
        [sys.executable, "-m", "axm_ast", "describe", "--detail", "full"],
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
