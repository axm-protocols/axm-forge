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

import pytest

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

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param(
                '[tool.uv.workspace]\nmembers = ["pkg-a", "pkg-b"]',
                ["pkg-a", "pkg-b"],
                id="single_line",
            ),
            pytest.param(
                '[tool.uv.workspace]\nmembers = [\n  "alpha",\n  "beta",\n]',
                ["alpha", "beta"],
                id="multiline",
            ),
            pytest.param(
                '[project]\nname = "foo"',
                [],
                id="no_section",
            ),
        ],
    )
    def test_parse_workspace_members(self, text: str, expected: list[str]) -> None:
        assert parse_workspace_members(text) == expected

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


@pytest.mark.parametrize(
    ("pkg_names", "edges", "forbidden_char", "label"),
    [
        pytest.param(
            ["axm.core", "axm.util"],
            [("axm.core", "axm.util")],
            ".",
            "Dot-name",
            id="dots_in_name",
        ),
        pytest.param(
            ["axm-engine", "axm-ast"],
            [("axm-engine", "axm-ast")],
            "-",
            "Hyphen-name",
            id="hyphens_in_name",
        ),
    ],
)
def test_workspace_mermaid_special_chars_in_name(
    pkg_names: list[str],
    edges: list[tuple[str, str]],
    forbidden_char: str,
    label: str,
) -> None:
    """Package names with `.` or `-` produce consistent underscored IDs."""
    ws = _make_ws(pkg_names=pkg_names, edges=edges)
    mermaid = format_workspace_graph_mermaid(ws)
    declared, edge_ids = _parse_mermaid(mermaid)
    missing = edge_ids - declared
    assert not missing, f"{label} IDs mismatch: {missing}\n{mermaid}"
    assert all(forbidden_char not in eid for eid in edge_ids), (
        f"{forbidden_char!r} survived in IDs"
    )
