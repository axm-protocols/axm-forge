"""Split from ``test_nodes.py``."""

from pathlib import Path

from axm_ast.models.nodes import PackageInfo


def test_dependency_edges() -> None:
    pkg = PackageInfo(
        name="test",
        root=Path("/test"),
        dependency_edges=[("core", "utils"), ("cli", "core")],
    )
    assert len(pkg.dependency_edges) == 2


def test_empty_package():
    pkg = PackageInfo(name="mypkg", root=Path("src/mypkg"))
    assert pkg.modules == []
    assert pkg.public_api == []
    assert pkg.module_names == []
