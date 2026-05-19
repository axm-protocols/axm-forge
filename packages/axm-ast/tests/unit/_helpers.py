"""Shared helpers for ``tests/unit``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.unit._helpers import <name>``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from tree_sitter import Node

_ANALYZER = "axm_ast.core.analyzer"
_EDGE_RE = re.compile(r"^\s+(\S+)\s+-->\s+(\S+)", re.MULTILINE)
_NODE_DECL_RE = re.compile(r'^\s+(\w+)\[".*"\]', re.MULTILINE)


def _first_node_of_type(root: Node, type_name: str) -> Node | None:
    for n in _walk(root):
        if n.type == type_name:
            return n
    return None


def _make_pyproject(path: Path, deps: list[str], *, build: str = "hatchling") -> None:
    """Write a minimal pyproject.toml."""
    dep_lines = ", ".join(f'"{d}"' for d in deps)
    (path / "pyproject.toml").write_text(
        f"[project]\n"
        f'name = "testpkg"\n'
        f"dependencies = [{dep_lines}]\n"
        f"[build-system]\n"
        f'requires = ["{build}"]\n'
        f'build-backend = "{build}.build"\n'
    )


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        yield from _walk(child)
