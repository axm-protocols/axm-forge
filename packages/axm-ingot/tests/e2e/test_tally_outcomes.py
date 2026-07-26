from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.e2e
def test_symbol_importable_from_package_root() -> None:
    """AC5: tally_outcomes imports from package root in a fresh interpreter."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from axm_ingot import tally_outcomes; print(callable(tally_outcomes))",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "True"
