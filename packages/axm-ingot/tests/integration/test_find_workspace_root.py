from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot.uv import find_workspace_root

pytestmark = pytest.mark.integration


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_walks_up_to_workspace_root(tmp_path: Path) -> None:
    """AC4: from a deep member dir, returns the workspace root."""
    _write(
        tmp_path / "pyproject.toml",
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n',
    )
    member = tmp_path / "packages" / "deep" / "src" / "nested"
    member.mkdir(parents=True, exist_ok=True)

    assert find_workspace_root(member) == tmp_path.resolve()


def test_returns_none_outside_workspace(tmp_path: Path) -> None:
    """AC4: a dir with no workspace parent returns None."""
    lonely = tmp_path / "nowhere" / "here"
    lonely.mkdir(parents=True, exist_ok=True)

    assert find_workspace_root(lonely) is None
