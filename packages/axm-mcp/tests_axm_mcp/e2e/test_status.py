"""E2E: ``axm-mcp status`` reports the not-running state deterministically."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_status(
    tmp_path: Path,
    cli_binary: str,
    free_port: int,
    sandbox_env: Callable[[Path], dict[str, str]],
) -> None:
    """``status`` on a not-running server parses and exits deterministically.

    Black-box: spawns the real binary via subprocess (no mocks) pointed at a
    sandboxed ``$HOME`` and an ephemeral port where nothing listens.
    """
    result = subprocess.run(  # noqa: S603
        [cli_binary, "status", "--host", "127.0.0.1", "--port", str(free_port)],
        capture_output=True,
        text=True,
        env=sandbox_env(tmp_path),
        timeout=30,
        check=False,
    )

    assert result.returncode == 1
    combined = (result.stdout + result.stderr).lower()
    assert "not running" in combined
