"""Unit tests for ES6/TypeScript import resolution and node dep-edges."""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.node_imports import node_module_name, resolve_node_edges
from axm_ast.models.nodes import ImportInfo, ModuleInfo


def _module(path: Path, root: Path, *imports: ImportInfo) -> ModuleInfo:
    """Build a ModuleInfo at *path* with the given imports."""
    return ModuleInfo(path=path, imports=list(imports))


def _rel_import(module: str) -> ImportInfo:
    """A relative ES6 import of *module*."""
    return ImportInfo(module=module, is_relative=True)


class TestNodeModuleName:
    """``node_module_name`` keys a module by its path relative to root."""

    def test_relative_posix_name(self, tmp_path: Path) -> None:
        """The name is the POSIX path relative to the package root."""
        f = tmp_path / "src" / "core" / "x.ts"
        assert node_module_name(f, tmp_path) == "src/core/x.ts"


class TestResolveNodeEdges:
    """``resolve_node_edges`` builds edges from resolved relative imports."""

    def test_relative_js_resolves_to_ts(self, tmp_path: Path) -> None:
        """A ``./util.js`` import resolves to the real ``util.ts`` sibling."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "util.ts").write_text("export const x = 1;")
        (src / "main.ts").write_text("import { x } from './util.js';")
        modules = [
            _module(src / "main.ts", tmp_path, _rel_import("./util.js")),
            _module(src / "util.ts", tmp_path),
        ]
        edges = resolve_node_edges(modules, tmp_path)
        assert edges == [("src/main.ts", "src/util.ts")]

    def test_directory_import_uses_index(self, tmp_path: Path) -> None:
        """A ``./lib`` import resolves to ``./lib/index.ts``."""
        src = tmp_path / "src"
        (src / "lib").mkdir(parents=True)
        (src / "lib" / "index.ts").write_text("export const t = 1;")
        (src / "a.ts").write_text("import { t } from './lib';")
        modules = [
            _module(src / "a.ts", tmp_path, _rel_import("./lib")),
            _module(src / "lib" / "index.ts", tmp_path),
        ]
        edges = resolve_node_edges(modules, tmp_path)
        assert edges == [("src/a.ts", "src/lib/index.ts")]

    def test_external_package_is_not_an_edge(self, tmp_path: Path) -> None:
        """A bare specifier (npm package) produces no internal edge."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.ts").write_text("import React from 'react';")
        external = ImportInfo(module="react", is_relative=False)
        modules = [_module(src / "a.ts", tmp_path, external)]
        assert resolve_node_edges(modules, tmp_path) == []

    def test_alias_import_is_not_an_edge(self, tmp_path: Path) -> None:
        """A non-relative alias ($lib/…) is treated as external (no edge)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.ts").write_text("import { z } from '$lib/util';")
        alias = ImportInfo(module="$lib/util", is_relative=False)
        modules = [_module(src / "a.ts", tmp_path, alias)]
        assert resolve_node_edges(modules, tmp_path) == []

    def test_unresolved_relative_is_skipped(self, tmp_path: Path) -> None:
        """A relative import to a missing file yields no edge (no crash)."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.ts").write_text("import { gone } from './missing.js';")
        modules = [_module(src / "a.ts", tmp_path, _rel_import("./missing.js"))]
        assert resolve_node_edges(modules, tmp_path) == []

    def test_no_self_edge(self, tmp_path: Path) -> None:
        """A module importing itself does not produce a self-edge."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.ts").write_text("import { x } from './a.js';")
        modules = [_module(src / "a.ts", tmp_path, _rel_import("./a.js"))]
        assert resolve_node_edges(modules, tmp_path) == []
