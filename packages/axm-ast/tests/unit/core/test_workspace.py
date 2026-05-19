"""Unit tests for axm_ast.core.workspace.

Covers pure-string parsing helpers (parse_workspace_members) and the
Mermaid graph formatter (format_workspace_graph_mermaid).

The ``_parse_workspace_members`` helper was promoted to the module-public
name ``parse_workspace_members`` because its contract is a deterministic
pure-string parse over a stable on-disk format (``[tool.uv.workspace]``
in ``pyproject.toml``) and tests assert directly on that contract.
It remains module-internal (not re-exported via ``axm_ast.__init__``).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from axm_ast.core.workspace import (
    format_workspace_graph_mermaid,
    parse_workspace_members,
)
from tests.unit._helpers import _EDGE_RE, _NODE_DECL_RE

# ────────────────────────────────────────────────────────────────────────────
# parse_workspace_members — pure-string parsing
# ────────────────────────────────────────────────────────────────────────────


class TestParsingUnit:
    """Pure-string parsing helpers (no I/O)."""

    def test_parse_workspace_members(self) -> None:
        text = '[tool.uv.workspace]\nmembers = ["pkg-a", "pkg-b"]'
        assert parse_workspace_members(text) == ["pkg-a", "pkg-b"]

    def test_parse_workspace_members_multiline(self) -> None:
        text = '[tool.uv.workspace]\nmembers = [\n  "alpha",\n  "beta",\n]'
        assert parse_workspace_members(text) == ["alpha", "beta"]

    def test_parse_workspace_members_no_section(self) -> None:
        text = '[project]\nname = "foo"'
        assert parse_workspace_members(text) == []

    def test_parse_workspace_members_glob(self) -> None:
        """parse_workspace_members returns raw glob strings unchanged."""
        text = '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        result = parse_workspace_members(text)
        assert result == ["packages/*"]


# ────────────────────────────────────────────────────────────────────────────
# format_workspace_graph_mermaid — node/edge consistency
# ────────────────────────────────────────────────────────────────────────────


def _make_ws(
    pkg_names: list[str],
    edges: list[tuple[str, str]],
) -> Any:
    """Build a minimal WorkspaceInfo-like object."""
    packages = [SimpleNamespace(name=n) for n in pkg_names]
    return SimpleNamespace(packages=packages, package_edges=edges)


def _parse_mermaid(mermaid: str) -> tuple[set[str], set[str]]:
    """Return (declared_ids, edge_ids) from mermaid text."""
    declared = {m.group(1) for m in _NODE_DECL_RE.finditer(mermaid)}
    edge_ids: set[str] = set()
    for m in _EDGE_RE.finditer(mermaid):
        edge_ids.add(m.group(1))
        edge_ids.add(m.group(2))
    return declared, edge_ids


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
