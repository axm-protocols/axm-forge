"""AXM MCP facade — compact tool surface over standard MCP primitives.

Instead of registering every discovered ``axm.tools`` entry point as an
individual MCP tool (one JSON-Schema each in ``tools/list``), the facade
exposes four meta-tools — ``axm_search`` / ``axm_describe`` / ``axm_call`` /
``axm_capabilities`` — plus a small *hot path* of frequently-used tools that
opt in via ``expose_directly = True``.  Everything else is reachable through
``axm_search`` -> ``axm_describe`` -> ``axm_call``, keeping the per-session
``tools/list`` payload small without depending on any client-specific
deferred-loading mechanism.

The catalog is built from the same ``discover_tools()`` dict the server
already holds — it does not re-import tools.
"""

from __future__ import annotations

from axm_mcp.facade.catalog import ToolCatalog

__all__ = ["ToolCatalog"]
