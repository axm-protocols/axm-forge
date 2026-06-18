from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot.uv import find_project_root

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "start_kind",
    [
        pytest.param("nested_dir", id="nearest-ancestor-from-nested-dir"),
        pytest.param("file", id="file-start-resolved-from-parent"),
    ],
)
def test_resolves_to_nearest_pyproject_ancestor(
    tmp_path: Path, start_kind: str
) -> None:
    """AC2: returns the nearest ancestor carrying any ``pyproject.toml`` (not
    only a ``[tool.uv.workspace]`` root), whether the start is a nested
    directory or a file (resolved from its parent)."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'plain'\nversion = '0.1.0'\n"
    )
    if start_kind == "nested_dir":
        start = tmp_path / "src" / "nested"
        start.mkdir(parents=True, exist_ok=True)
    else:
        start = tmp_path / "pkg" / "mod.py"
        start.parent.mkdir(parents=True, exist_ok=True)
        start.write_text("x = 1\n")

    assert find_project_root(start) == tmp_path.resolve()


def test_falls_back_to_start_directory_when_no_pyproject(tmp_path: Path) -> None:
    """AC2: with no ``pyproject.toml`` in any ancestor, returns the start
    directory (resolved) — never ``None``."""
    lonely = tmp_path / "nowhere" / "here"
    lonely.mkdir(parents=True, exist_ok=True)

    result = find_project_root(lonely)

    assert result == lonely.resolve()
    assert result is not None
