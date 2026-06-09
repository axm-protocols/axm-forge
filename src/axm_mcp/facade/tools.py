"""Register the four facade meta-tools on a FastMCP server.

``register_facade(mcp, catalog)`` wires ``axm_search`` / ``axm_describe`` /
``axm_call`` / ``axm_capabilities`` to a :class:`~axm_mcp.facade.catalog.ToolCatalog`.
Each returns a plain ``dict`` (or, for ``axm_call``, a ``str``) so FastMCP
renders it without extra schema work.

``axm_call`` translates an :class:`UnknownToolError` into a structured error
payload and, on a ``TypeError`` from bad kwargs, appends the accepted-params
hint — the mitigation the spec mandates for the loss of client-side schema
validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_mcp.facade.catalog import ToolCatalog, UnknownToolError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

__all__ = ["FACADE_TOOLS", "register_facade"]

#: Names + descriptions of the facade tools, for the ``list_tools`` listing.
FACADE_TOOLS: dict[str, str] = {
    "axm_search": (
        "Search the AXM tool catalog by keyword/tag; returns name+summary+domain+tags."
    ),
    "axm_describe": (
        "Return the full invocation contract (typed params + docstring) for one tool."
    ),
    "axm_call": "Execute an AXM tool by name; returns its text output.",
    "axm_capabilities": (
        "List AXM tools grouped by domain (ast, git, ticket, bib, audit, …)."
    ),
}


def register_facade(  # type: ignore[explicit-any]  # FastMCP tool-schema boundary
    mcp: FastMCP, catalog: ToolCatalog
) -> None:
    """Register the four facade meta-tools against *catalog*.

    Args:
        mcp: FastMCP server instance.
        catalog: The tool catalog the meta-tools delegate to.
    """

    @mcp.tool(name="axm_search")
    def axm_search(
        query: str = "",
        domain: str | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        """Search the AXM tool catalog.

        Args:
            query: Case-insensitive substring matched against name, summary,
                tags and domain. Empty lists everything (browsable).
            domain: Optional exact-match domain filter (e.g. "git").
            limit: Maximum number of results (default 20).

        Returns:
            ``{results: [{name, summary, domain, tags}], count}``.
        """
        hits = catalog.search(query, domain=domain, limit=limit)
        return {"results": hits, "count": len(hits)}

    @mcp.tool(name="axm_describe")
    def axm_describe(name: str) -> dict[str, object]:
        """Return the full invocation contract for one tool.

        Args:
            name: The tool's name (as listed by ``axm_search``).

        Returns:
            ``{name, summary, domain, tags, docstring, params}`` — or
            ``{error}`` if the tool is unknown.
        """
        try:
            return catalog.describe(name)
        except UnknownToolError as exc:
            return {"error": str(exc)}

    @mcp.tool(name="axm_call")
    def axm_call(name: str, arguments: dict[str, object] | None = None) -> str:
        """Execute an AXM tool by name and return its text output.

        Args:
            name: The tool's name.
            arguments: Keyword arguments for the tool.

        Returns:
            The tool's pre-rendered text (or a rendering of its data). On
            error, a message — including the accepted parameters when the
            arguments did not match the tool's signature.
        """
        try:
            return catalog.call(name, arguments)
        except UnknownToolError as exc:
            return f"error: {exc}"
        except TypeError as exc:
            hint = catalog.param_hint(name)
            suffix = f" — accepted params: {hint}" if hint else ""
            return f"error: bad arguments for {name!r}: {exc}{suffix}"

    @mcp.tool(name="axm_capabilities")
    def axm_capabilities(domain: str | None = None) -> dict[str, object]:
        """List AXM tools grouped by domain.

        Args:
            domain: Optional single domain to return.

        Returns:
            ``{domains: {domain: [names]}, count}``.
        """
        groups = catalog.capabilities(domain=domain)
        total = sum(len(v) for v in groups.values())
        return {"domains": groups, "count": total}
