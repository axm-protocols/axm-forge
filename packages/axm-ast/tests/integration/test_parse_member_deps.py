"""Split from ``test_workspace.py``."""

from pathlib import Path

from axm_ast.core.workspace import _parse_member_deps


def _make_pyproject(path: Path, name: str, deps: list[str] | None = None) -> None:
    """Write a minimal pyproject.toml for a workspace member."""
    dep_lines = ""
    if deps:
        dep_strs = ", ".join(f'"{d}"' for d in deps)
        dep_lines = f"dependencies = [{dep_strs}]"
    else:
        dep_lines = "dependencies = []"

    path.write_text(
        f"""\
[project]
name = "{name}"
version = "0.1.0"
{dep_lines}
""",
        encoding="utf-8",
    )


def test_parse_member_deps(tmp_path: Path) -> None:
    _make_pyproject(tmp_path / "pyproject.toml", "test", ["dep-a>=1.0", "dep-b"])
    deps = _parse_member_deps(tmp_path)
    assert "dep-a" in deps
    assert "dep-b" in deps


def test_parse_member_deps_no_pyproject(tmp_path: Path) -> None:
    assert _parse_member_deps(tmp_path) == []
