"""Tests for the decoupled FastMCP server configuration.

Merged from aspect-split mirror sources:
- test_mcp_app.py       (server config + main() existence)
- test_coverage_gaps.py (main() delegation to mcp.run, package entry point)
"""

from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

import pytest

from axm_mcp import mcp_app


class TestMCPServer:
    """Tests for FastMCP server configuration."""

    def test_server_name(self) -> None:
        """Server has correct name."""
        assert mcp_app.mcp.name == "axm-mcp"

    def test_discovery_ran(self) -> None:
        """Tool discovery ran (may be empty if no axm-* packages installed)."""
        assert isinstance(mcp_app.discovered_tools, dict)

    def test_main_function_exists(self) -> None:
        """main() entry point exists."""
        assert callable(mcp_app.main)


class TestMcpAppMain:
    """Cover main() in mcp_app.py (line 47)."""

    def test_main_calls_run(self) -> None:
        """main() delegates to mcp.run()."""
        with patch("axm_mcp.mcp_app.mcp") as mock_mcp:
            from axm_mcp.mcp_app import main

            main()
            mock_mcp.run.assert_called_once()


class TestInitMain:
    """Cover main() in __init__.py (lines 10-12)."""

    def test_init_main_calls_run(self) -> None:
        """Package-level main() routes through CLI to mcp.run() (stdio)."""
        with (
            patch("axm_mcp.mcp_app.mcp") as mock_mcp,
            patch("sys.argv", ["axm-mcp"]),
        ):
            import axm_mcp

            with pytest.raises(SystemExit, match="0"):
                axm_mcp.main()
            mock_mcp.run.assert_called_once()


class TestDecouplingShape:
    """Pure-import decoupling invariants on the discovery shell (no I/O)."""

    @pytest.mark.parametrize(
        "func_name",
        ["init", "check", "resume", "read", "configure", "get_orchestrator"],
        ids=["init", "check", "resume", "read", "configure", "get_orchestrator"],
    )
    def test_no_hardcoded_protocol_function(self, func_name: str) -> None:
        """mcp_app discovers tools dynamically; it hardcodes no protocol func."""
        attr = getattr(mcp_app, func_name, None)
        assert attr is None or not callable(attr), (
            f"{func_name}() is hardcoded in mcp_app"
        )

    def test_legacy_server_package_removed(self) -> None:
        """The legacy ``server/`` sub-package is no longer importable."""
        with pytest.raises(ModuleNotFoundError):
            import_module("axm_mcp.server.app")
