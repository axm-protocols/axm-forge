"""Split from ``test_workspace_context_detection.py``."""

from pathlib import Path
from textwrap import dedent

from axm_init.checks._workspace import (
    ProjectContext,
    detect_context,
    find_workspace_root,
)


def test_nested_workspaces(tmp_path: Path) -> None:
    """Workspace inside another workspace → detects nearest parent."""
    # Outer workspace
    (tmp_path / "pyproject.toml").write_text(
        dedent("""\
            [project]
            name = "outer"

            [tool.uv.workspace]
            members = ["inner"]
        """)
    )
    # Inner workspace (also a workspace root itself)
    inner = tmp_path / "inner"
    inner.mkdir()
    (inner / "pyproject.toml").write_text(
        dedent("""\
            [project]
            name = "inner"

            [tool.uv.workspace]
            members = ["packages/*"]
        """)
    )
    # Inner is itself a WORKSPACE (it has [tool.uv.workspace])
    assert detect_context(inner) == ProjectContext.WORKSPACE

    # A package inside inner should find inner as root, not outer
    pkg = inner / "packages" / "deep"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text('[project]\nname = "deep"\n')
    root = find_workspace_root(pkg)
    assert root is not None
    assert root.resolve() == inner.resolve()
