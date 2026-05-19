"""Tests covering ``analyze_package`` together with ``build_import_graph``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast import analyze_package
from axm_ast.core.analyzer import build_import_graph


@pytest.mark.functional
def test_venv_not_in_graph(tmp_path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""My package."""')
    venv = pkg / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "dep.py").write_text("x = 1")

    result = analyze_package(pkg)
    graph = build_import_graph(result)
    all_nodes = set(graph.keys())
    for targets in graph.values():
        all_nodes.update(targets)
    assert not any("dep" in n for n in all_nodes)


@pytest.mark.integration
class TestImportEdges:
    """Intra-package imports (absolute and relative) create dependency edges."""

    @pytest.mark.parametrize(
        ("files", "src_module", "target_module"),
        [
            pytest.param(
                {
                    "__init__.py": "",
                    "sub.py": "x = 1\n",
                    "main.py": "from mypkg.sub import x\n",
                },
                "main",
                "sub",
                id="absolute_sibling",
            ),
            pytest.param(
                {
                    "__init__.py": "",
                    "core/__init__.py": "",
                    "core/engine.py": "def run() -> None: ...\n",
                    "cli.py": "from mypkg.core.engine import run\n",
                },
                "cli",
                "core.engine",
                id="absolute_nested",
            ),
            pytest.param(
                {
                    "__init__.py": "VERSION = '1.0'\n",
                    "info.py": "from mypkg import VERSION\n",
                },
                "info",
                "mypkg",
                id="absolute_to_package_root",
            ),
            pytest.param(
                {
                    "__init__.py": "",
                    "sub.py": "x = 1\n",
                    "main.py": "from .sub import x\n",
                },
                "main",
                "sub",
                id="relative_sibling",
            ),
        ],
    )
    def test_import_creates_edge(
        self,
        tmp_path: Path,
        files: dict[str, str],
        src_module: str,
        target_module: str,
    ) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        for rel, content in files.items():
            fp = pkg / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        assert src_module in graph
        assert target_module in graph[src_module]

    def test_external_import_no_edge(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("from pathlib import Path\nimport os\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        assert "mod" not in graph

    def test_self_import_no_edge(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "mod.py").write_text("from mypkg.mod import something\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        if "mod" in graph:
            assert "mod" not in graph["mod"]


@pytest.mark.integration
class TestMixedImports:
    """Packages using both absolute and relative imports."""

    def test_both_create_edges(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("x = 1\n")
        (pkg / "b.py").write_text("y = 2\n")
        (pkg / "c.py").write_text("from .a import x\nfrom mypkg.b import y\n")

        result = analyze_package(pkg)
        graph = build_import_graph(result)
        assert "c" in graph
        targets = graph["c"]
        assert "a" in targets
        assert "b" in targets


@pytest.mark.integration
class TestRealProjectGraph:
    """Smoke test on axm-ast source itself."""

    def test_axm_ast_has_edges(self) -> None:
        src = Path(__file__).resolve().parents[2] / "src" / "axm_ast"
        if not src.is_dir():
            pytest.skip("Source not available")
        result = analyze_package(src)
        graph = build_import_graph(result)
        assert len(graph) > 0
        total_edges = sum(len(v) for v in graph.values())
        assert total_edges >= 1
