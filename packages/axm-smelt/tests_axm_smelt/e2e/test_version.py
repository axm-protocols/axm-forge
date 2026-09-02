"""End-to-end regression test for the surviving package version API."""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.e2e
def test_package_version_remains_importable() -> None:
    """The façade removal preserves the package's public version."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import axm_smelt; print(axm_smelt.__version__)",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
