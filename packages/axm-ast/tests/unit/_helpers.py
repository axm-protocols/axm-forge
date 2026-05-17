"""Shared helpers for ``tests/unit``.

Promoted from duplicate top-level defs found across files.
Import explicitly: ``from tests.unit._helpers import <name>``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


@dataclass
class _StubClass:
    name: str
    line_start: int = 1
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    methods: list[_StubMethod] = field(default_factory=list)


@dataclass
class _StubContext:
    entry_points: set[str] = field(default_factory=set)
    all_refs: set[str] = field(default_factory=set)
    extra_pkg: object | None = None
    namespace_modules: set[Path] = field(default_factory=set)


@dataclass
class _StubMethod:
    name: str
    line_start: int = 1
    decorators: list[str] = field(default_factory=list)


@dataclass
class _StubModule:
    path: Path = field(default_factory=lambda: Path("/fake/module.py"))
    classes: list[_StubClass] = field(default_factory=list)
    all_exports: list[str] | None = None


def _cls(name: str, bases: list[str], methods: list[Any] | None = None) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(name=name, bases=bases, methods=methods or [])


def _method(name: str, line_start: int = 1) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(name=name, line_start=line_start)


def _no_callers(_pkg_arg: Any, _name: str) -> list[Any]:
    return []


def _override_mod(classes: list[Any], path: str = "mod.py") -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(classes=classes, path=path)


def _override_pkg(modules: list[Any]) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(modules=modules)
