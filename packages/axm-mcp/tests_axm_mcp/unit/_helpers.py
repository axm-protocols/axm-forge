"""Shared helpers for ``tests/unit``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests_axm_mcp.unit._helpers import <name>``.
"""

from __future__ import annotations

from typing import Any, cast

from axm_mcp.discovery import ToolEntry
from axm_mcp.facade.catalog import ToolCatalog

_DISCOVER = "axm_mcp.discovery.importlib.metadata.entry_points"


class FakeMCP:
    """Minimal FastMCP stand-in that captures registered tools."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, *, name: str) -> Any:
        def decorator(fn: Any) -> Any:
            self.tools[name] = fn
            return fn

        return decorator


def _catalog(**tools: object) -> ToolCatalog:
    """Build a catalog from fake tools, casting to the ToolEntry contract."""
    return ToolCatalog({k: cast(ToolEntry, v) for k, v in tools.items()})
