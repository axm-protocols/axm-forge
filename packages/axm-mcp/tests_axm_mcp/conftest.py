"""Pytest fixtures auto-discovered by tests in this directory.

Promoted from duplicate ``@pytest.fixture`` definitions originally
scattered across multiple test files.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_mcp import wrapping


@pytest.fixture
def tmp_pid_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Redirect PID file to a temp directory."""
    pid_file = tmp_path / "mcp-server.pid"
    with (
        patch("axm_mcp.cli.PID_DIR", tmp_path),
        patch("axm_mcp.cli.PID_FILE", pid_file),
    ):
        yield pid_file


@pytest.fixture
def _restore_http_mode() -> Iterator[None]:
    """Save and restore the module-global ``_HTTP_MODE`` around each test.

    The flag is process-global; serving flips it. We snapshot and restore so
    one test's serve path cannot leak ``True`` into another test.
    """
    saved = wrapping._HTTP_MODE
    try:
        yield
    finally:
        wrapping._HTTP_MODE = saved
