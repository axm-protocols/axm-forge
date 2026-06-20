"""Unit tests for the node/TypeScript branch of ``analyze_package``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import _is_node_project, analyze_package

pytest.importorskip("tree_sitter_typescript")


def _node_project(tmp_path: Path) -> Path:
    """Create a minimal node project with one TS module."""
    (tmp_path / "package.json").write_text('{"name":"pkg"}')
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.ts").write_text(
        "export function greet(): string { return 'hi'; }\n"
        "export interface User { id: number; }\n"
    )
    return tmp_path


class TestIsNodeProject:
    """``_is_node_project`` distinguishes node from Python packages."""

    def test_package_json_without_init_is_node(self, tmp_path: Path) -> None:
        """package.json and no __init__.py → node project."""
        (tmp_path / "package.json").write_text("{}")
        assert _is_node_project(tmp_path) is True

    def test_python_src_layout_is_not_node(self, tmp_path: Path) -> None:
        """A package.json beside a Python src layout is NOT treated as node."""
        (tmp_path / "package.json").write_text("{}")
        pkg = tmp_path / "src" / "mylib"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        assert _is_node_project(tmp_path) is False

    def test_no_package_json_is_not_node(self, tmp_path: Path) -> None:
        """No package.json → not a node project."""
        assert _is_node_project(tmp_path) is False


class TestAnalyzeNodePackage:
    """``analyze_package`` routes node projects through the TS path."""

    def test_discovers_and_extracts_ts_modules(self, tmp_path: Path) -> None:
        """The node project's TS file is discovered and its symbols extracted."""
        root = _node_project(tmp_path)
        pkg = analyze_package(root)
        assert [m.path.name for m in pkg.modules] == ["index.ts"]
        mod = pkg.modules[0]
        assert "greet" in {f.name for f in mod.functions}
        assert "User" in {c.name for c in mod.classes}

    def test_node_package_resolves_es6_edges(self, tmp_path: Path) -> None:
        """Relative ES6 imports build the package's dependency edges."""
        root = _node_project(tmp_path)
        src = root / "src"
        (src / "util.ts").write_text("export const x = 1;\n")
        (src / "index.ts").write_text("import { x } from './util.js';\n")
        pkg = analyze_package(root)
        assert ("src/index.ts", "src/util.ts") in pkg.dependency_edges

    def test_skips_declaration_files(self, tmp_path: Path) -> None:
        """``.d.ts`` declaration files are not treated as source modules."""
        root = _node_project(tmp_path)
        (root / "src" / "types.d.ts").write_text("export declare const x: number;\n")
        pkg = analyze_package(root)
        assert [m.path.name for m in pkg.modules] == ["index.ts"]
