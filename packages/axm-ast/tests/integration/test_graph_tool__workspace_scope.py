"""Integration tests for GraphTool.execute with the ``scope`` parameter.

Real filesystem I/O — a tmp uv workspace with two cross-importing packages.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.tools.graph import GraphTool

pytestmark = pytest.mark.integration


def _write_pkg(
    root: Path,
    pkg_dir: str,
    dist_name: str,
    import_name: str,
    files: dict[str, str],
) -> None:
    """Scaffold a workspace member package under ``root/pkg_dir``."""
    pkg_root = root / pkg_dir
    src = pkg_root / "src" / import_name
    src.mkdir(parents=True, exist_ok=True)
    (pkg_root / "pyproject.toml").write_text(
        f'[project]\nname = "{dist_name}"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n'
    )
    (src / "__init__.py").write_text("")
    for rel, content in files.items():
        (src / rel).write_text(content)


@pytest.fixture
def mini_workspace(tmp_path: Path) -> Path:
    """Create a 2-package uv workspace where pkg_a imports from pkg_b."""
    root = tmp_path / "ws"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    (root / "packages").mkdir()
    _write_pkg(
        root,
        "packages/pkg_b",
        "pkg-b",
        "pkg_b",
        {"util.py": "VALUE = 1\n"},
    )
    _write_pkg(
        root,
        "packages/pkg_a",
        "pkg-a",
        "pkg_a",
        {
            "core.py": "X = 1\n",
            "cli.py": "from pkg_a import core\nfrom pkg_b import util\n",
        },
    )
    return root


def test_execute_scope_workspace_module_graph(mini_workspace: Path) -> None:
    """AC2, AC5: scope=workspace yields namespaced nodes + cross-package edge."""
    result = GraphTool().execute(
        path=str(mini_workspace), scope="workspace", format="json"
    )
    assert result.success, result.error
    graph = result.data["graph"]
    nodes = set(graph) | {t for ts in graph.values() for t in ts}
    # every node is namespaced {pkg}.{module}
    assert all("." in n for n in nodes)
    assert any(n.startswith("pkg_a.") for n in nodes)
    assert any(n.startswith("pkg_b.") for n in nodes)
    # cross-package edge pkg_a.cli -> pkg_b.util
    cli_targets = graph.get("pkg_a.cli", [])
    assert "pkg_b.util" in cli_targets


def test_execute_scope_omitted_backward_compatible(mini_workspace: Path) -> None:
    """AC3: omitting scope keeps today's package-level dep graph at a ws root."""
    result = GraphTool().execute(path=str(mini_workspace), format="json")
    assert result.success, result.error
    # package-level graph: bare package names, no {pkg}.{module} namespacing
    nodes = result.data["nodes"]
    assert all("." not in n for n in nodes)
    assert "pkg_a" in nodes
    assert "pkg_b" in nodes
