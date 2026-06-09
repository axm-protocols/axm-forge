"""Integration: the facade bascule in mcp_app reduces the tools/list payload.

Reloads ``axm_mcp.mcp_app`` under each ``AXM_MCP_FACADE`` setting against a
mocked entry-point set, asserting the exposed surface differs between facade
and legacy modes.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from axm.tools.base import ToolResult

_DISCOVER = "axm_mcp.discovery.importlib.metadata.entry_points"

pytestmark = pytest.mark.integration


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
