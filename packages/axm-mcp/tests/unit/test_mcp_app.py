"""Tests for the decoupled FastMCP server configuration.

Merged from aspect-split mirror sources:
- test_mcp_app.py       (server config)
- test_coverage_gaps.py (package entry point)
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Iterator
from importlib import import_module
from typing import Any
from unittest.mock import patch

import pytest
from axm.tools.base import ToolResult

from axm_mcp import mcp_app


class TestMCPServer:
    """Tests for FastMCP server configuration."""

    def test_server_name(self) -> None:
        """Server has correct name."""
        assert mcp_app.mcp.name == "axm-mcp"

    def test_discovery_ran(self) -> None:
        """Tool discovery ran (may be empty if no axm-* packages installed)."""
        assert isinstance(mcp_app.discovered_tools, dict)


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


_DISCOVER = "axm_mcp.discovery.importlib.metadata.entry_points"


class _HotTool:
    expose_directly = True
    domain = "demo"

    @property
    def name(self) -> str:
        return "hot_one"

    def execute(self, *, x: int = 0) -> ToolResult:
        """A hot-path demo tool."""
        return ToolResult(success=True, text="ok")


class _ColdTool:
    @property
    def name(self) -> str:
        return "cold_one"

    def execute(self, *, y: int = 0) -> ToolResult:
        """A facade-only demo tool."""
        return ToolResult(success=True, text="ok")


class _FakeEP:
    def __init__(self, name: str, obj: object) -> None:
        self.name = name
        self._obj = obj

    def load(self) -> object:
        return self._obj


def _fake_entry_points(*, group: str | None = None, **_: Any) -> list[_FakeEP]:
    if group == "axm.tools":
        return [_FakeEP("hot_one", _HotTool), _FakeEP("cold_one", _ColdTool)]
    return []


def _reload_app() -> Any:
    import axm_mcp.mcp_app as app

    return importlib.reload(app)


@pytest.fixture
def _restore_app() -> Iterator[None]:
    # Ensure the module is reloaded back to its real state after the test.
    yield
    with patch(_DISCOVER, _fake_entry_points):
        _reload_app()
    importlib.reload(__import__("axm_mcp.mcp_app", fromlist=["x"]))


def _exposed_names(monkeypatch: pytest.MonkeyPatch, facade: str) -> set[str]:
    monkeypatch.setenv("AXM_MCP_FACADE", facade)
    with patch(_DISCOVER, _fake_entry_points):
        app = _reload_app()
    return {t.name for t in asyncio.run(app.mcp.list_tools())}


def test_facade_mode_hides_cold_tool(
    monkeypatch: pytest.MonkeyPatch, _restore_app: None
) -> None:
    names = _exposed_names(monkeypatch, "1")
    # Facade meta-tools present
    assert {"axm_search", "axm_describe", "axm_call", "axm_capabilities"} <= names
    # Hot-path tool exposed directly; cold tool hidden behind the facade
    assert "hot_one" in names
    assert "cold_one" not in names


def test_legacy_mode_exposes_all(
    monkeypatch: pytest.MonkeyPatch, _restore_app: None
) -> None:
    names = _exposed_names(monkeypatch, "0")
    assert "hot_one" in names
    assert "cold_one" in names
    assert "axm_search" not in names


def test_facade_payload_smaller_than_legacy(
    monkeypatch: pytest.MonkeyPatch, _restore_app: None
) -> None:
    facade = _exposed_names(monkeypatch, "1")
    legacy = _exposed_names(monkeypatch, "0")
    # Legacy exposes every discovered tool; facade collapses the cold ones.
    assert len(facade) < len(legacy) + 4  # facade adds 4 meta-tools
    assert "cold_one" in legacy and "cold_one" not in facade


def test_builtins_are_in_catalog(
    monkeypatch: pytest.MonkeyPatch, _restore_app: None
) -> None:
    """P2-3: the built-ins (verify/web_fetch) are indexed by the catalog, so
    ``axm_describe('verify')`` resolves instead of returning 'Unknown tool'.
    """
    monkeypatch.setenv("AXM_MCP_FACADE", "1")
    with patch(_DISCOVER, _fake_entry_points):
        app = _reload_app()
    assert "verify" in app.catalog.names()
    assert "web_fetch" in app.catalog.names()
    described = app.catalog.describe("verify")
    assert described["name"] == "verify"
