from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

from axm_ast.core.workspace import format_workspace_graph_mermaid


def _make_ws(
    pkg_names: list[str],
    edges: list[tuple[str, str]],
) -> Any:
    """Build a minimal WorkspaceInfo-like object."""
    packages = [SimpleNamespace(name=n) for n in pkg_names]
    return SimpleNamespace(packages=packages, package_edges=edges)


_NODE_DECL_RE = re.compile(r'^\s+(\w+)\[".*"\]', re.MULTILINE)
_EDGE_RE = re.compile(r"^\s+(\S+)\s+-->\s+(\S+)", re.MULTILINE)


def _parse_mermaid(mermaid: str) -> tuple[set[str], set[str]]:
    """Return (declared_ids, edge_ids) from mermaid text."""
    declared = {m.group(1) for m in _NODE_DECL_RE.finditer(mermaid)}
    edge_ids: set[str] = set()
    for m in _EDGE_RE.finditer(mermaid):
        edge_ids.add(m.group(1))
        edge_ids.add(m.group(2))
    return declared, edge_ids


# ── Unit tests ────────────────────────────────────────────────────────


def test_workspace_mermaid_node_edge_consistency() -> None:
    """Every node ID in edges must appear in a node declaration line."""
    ws = _make_ws(
        pkg_names=["axm-engine", "axm-mcp", "axm"],
        edges=[("axm-engine", "axm"), ("axm-mcp", "axm")],
    )
    mermaid = format_workspace_graph_mermaid(ws)
    declared, edge_ids = _parse_mermaid(mermaid)
    missing = edge_ids - declared
    assert not missing, f"Edge IDs not declared as nodes: {missing}\n{mermaid}"


def test_workspace_mermaid_no_path_prefix() -> None:
    """No edge line should contain '/' in node IDs."""
    ws = _make_ws(
        pkg_names=["axm-engine", "axm-mcp", "axm"],
        edges=[("axm-engine", "axm"), ("axm-mcp", "axm")],
    )
    mermaid = format_workspace_graph_mermaid(ws)
    _, edge_ids = _parse_mermaid(mermaid)
    slash_ids = {eid for eid in edge_ids if "/" in eid}
    assert not slash_ids, f"Edge IDs contain '/': {slash_ids}\n{mermaid}"


# ── Edge cases ────────────────────────────────────────────────────────


def test_workspace_mermaid_dots_in_name() -> None:
    """Package names with dots produce consistent underscored IDs."""
    ws = _make_ws(
        pkg_names=["axm.core", "axm.util"],
        edges=[("axm.core", "axm.util")],
    )
    mermaid = format_workspace_graph_mermaid(ws)
    declared, edge_ids = _parse_mermaid(mermaid)
    missing = edge_ids - declared
    assert not missing, f"Dot-name IDs mismatch: {missing}\n{mermaid}"
    assert all("." not in eid for eid in edge_ids), "Dots survived in IDs"


def test_workspace_mermaid_hyphens_in_name() -> None:
    """Package names with hyphens produce consistent underscored IDs."""
    ws = _make_ws(
        pkg_names=["axm-engine", "axm-ast"],
        edges=[("axm-engine", "axm-ast")],
    )
    mermaid = format_workspace_graph_mermaid(ws)
    declared, edge_ids = _parse_mermaid(mermaid)
    missing = edge_ids - declared
    assert not missing, f"Hyphen-name IDs mismatch: {missing}\n{mermaid}"
    assert all("-" not in eid for eid in edge_ids), "Hyphens survived in IDs"
