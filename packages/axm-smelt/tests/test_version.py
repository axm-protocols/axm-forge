"""Test package version and public API."""

from __future__ import annotations

import subprocess
import sys


def test_version_importable() -> None:
    from axm_smelt import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_public_api_exports() -> None:
    import axm_smelt

    assert hasattr(axm_smelt, "__all__")
    assert "__version__" in axm_smelt.__all__


def test_cli_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "axm_smelt.cli", "version"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Fallback: try the script entry point
    if result.returncode != 0:
        result = subprocess.run(
            [sys.executable, "-m", "axm_smelt.cli", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    assert result.returncode == 0
    assert len(result.stdout.strip()) > 0
