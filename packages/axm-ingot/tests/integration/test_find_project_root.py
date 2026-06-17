from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot.uv import find_project_root

pytestmark = pytest.mark.integration


def test_returns_first_ancestor_with_any_pyproject(tmp_path: Path) -> None:
    """AC2: returns the nearest ancestor carrying any ``pyproject.toml``,
    not only a ``[tool.uv.workspace]`` root."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'plain'\nversion = '0.1.0'\n"
    )
    deep = tmp_path / "src" / "nested"
    deep.mkdir(parents=True, exist_ok=True)

    assert find_project_root(deep) == tmp_path.resolve()


def test_accepts_a_file_and_uses_its_parent(tmp_path: Path) -> None:
    """AC2: a file start is resolved from its parent directory."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'plain'\nversion = '0.1.0'\n"
    )
    module = tmp_path / "pkg" / "mod.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("x = 1\n")

    assert find_project_root(module) == tmp_path.resolve()


def test_falls_back_to_start_directory_when_no_pyproject(tmp_path: Path) -> None:
    """AC2: with no ``pyproject.toml`` in any ancestor, returns the start
    directory (resolved) — never ``None``."""
    lonely = tmp_path / "nowhere" / "here"
    lonely.mkdir(parents=True, exist_ok=True)

    result = find_project_root(lonely)

    assert result == lonely.resolve()
    assert result is not None
