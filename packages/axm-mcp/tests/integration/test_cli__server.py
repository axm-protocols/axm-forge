"""Integration: the real production serve paths and the _HTTP_MODE wiring.

These tests exercise the real entry chains (cli.serve -> server.serve, and
the stdio default) with only ``mcp.run`` mocked out (no subprocess, no real
bind). They assert the side effect on ``wrapping._HTTP_MODE`` *without ever
patching the flag* — this is the exact false-green gap that hid the bug: the
unit tests patched the flag, so they could never see that production never
set it.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from axm_mcp import cli, server, wrapping

pytestmark = pytest.mark.integration


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


def test_serve_path_enables_http_mode(_restore_http_mode: None) -> None:
    """AC4: the real HTTP serve path sets ``wrapping._HTTP_MODE`` to True.

    Drives ``server.serve`` (reached in production via ``cli.serve``) with
    only ``mcp.run`` mocked. The flag is NOT patched: we assert the wiring
    actually flips it before ``mcp.run`` is entered.
    """
    wrapping._HTTP_MODE = False  # start from the stdio default, no patching
    with patch("axm_mcp.server.mcp") as mock_mcp:
        server.serve()
    mock_mcp.run.assert_called_once_with(transport="streamable-http")
    assert wrapping._HTTP_MODE is True


def test_cli_serve_enables_http_mode(_restore_http_mode: None) -> None:
    """AC1, AC4: the full ``cli.serve`` chain enables HTTP mode.

    Covers the production chain cli.serve -> server.serve -> mcp.run with
    ``mcp.run`` mocked. PID file side effects are tolerated (real tmp I/O).
    The flag is asserted, never patched.
    """
    wrapping._HTTP_MODE = False
    with (
        patch("axm_mcp.server.mcp") as mock_mcp,
        patch("axm_mcp.cli.write_pid"),
        patch("axm_mcp.cli.remove_pid_file"),
    ):
        cli.serve()
    mock_mcp.run.assert_called_once_with(transport="streamable-http")
    assert wrapping._HTTP_MODE is True


def test_stdio_path_leaves_http_mode_false(_restore_http_mode: None) -> None:
    """AC1: the stdio default entry leaves ``wrapping._HTTP_MODE`` False.

    Stdio is one process per conversation — no cross-session contention — so
    the lock must stay disengaged. Drives the real ``cli`` stdio default with
    ``mcp.run`` mocked; the flag is asserted, never patched.
    """
    wrapping._HTTP_MODE = False
    with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
        cli._stdio()
    mock_mcp.run.assert_called_once_with()
    assert wrapping._HTTP_MODE is False
