"""Split from ``test_workspace_glob.py``."""

from pathlib import Path

from axm_ast.core.workspace import _build_package_edges


def test_build_package_edges_glob(tmp_path: Path) -> None:
    """_build_package_edges finds edges with expanded glob paths."""
    pkg_a = tmp_path / "packages" / "pkg-a"
    pkg_b = tmp_path / "packages" / "pkg-b"
    pkg_a.mkdir(parents=True)
    pkg_b.mkdir(parents=True)
    (pkg_a / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nversion = "0.1.0"\ndependencies = []\n'
    )
    (pkg_b / "pyproject.toml").write_text(
        '[project]\nname = "pkg-b"\nversion = "0.1.0"\ndependencies = ["pkg-a"]\n'
    )

    members = ["packages/pkg-a", "packages/pkg-b"]
    member_names = set(members)
    edges = _build_package_edges(tmp_path, members, member_names)
    assert len(edges) > 0
