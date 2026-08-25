from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.dependencies import resolve_workspace_members

pytestmark = pytest.mark.integration


def _write_pyproject(path: Path, content: str = "") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(content)


def _package() -> str:
    return '[project]\nname = "pkg"\nversion = "0.1.0"\n'


def test_returns_member_paths(tmp_path: Path) -> None:
    """AC1, AC2: a real uv workspace resolves to the list of member paths."""
    _write_pyproject(
        tmp_path,
        textwrap.dedent(
            """\
            [tool.uv.workspace]
            members = ["packages/*"]
            """
        ),
    )
    _write_pyproject(tmp_path / "packages" / "pkg-a", _package())
    _write_pyproject(tmp_path / "packages" / "pkg-b", _package())

    members = resolve_workspace_members(tmp_path)

    assert members is not None
    assert sorted(p.name for p in members) == ["pkg-a", "pkg-b"]
    assert all(isinstance(p, Path) for p in members)


def test_excluded_member_absent(tmp_path: Path) -> None:
    """AC3: a member listed in ``exclude`` does not appear in the result."""
    _write_pyproject(
        tmp_path,
        textwrap.dedent(
            """\
            [tool.uv.workspace]
            members = ["packages/*"]
            exclude = ["packages/pkg-excluded"]
            """
        ),
    )
    _write_pyproject(tmp_path / "packages" / "pkg-a", _package())
    _write_pyproject(tmp_path / "packages" / "pkg-excluded", _package())

    members = resolve_workspace_members(tmp_path)

    assert members is not None
    names = {p.name for p in members}
    assert "pkg-a" in names
    assert "pkg-excluded" not in names


def test_none_when_not_workspace(tmp_path: Path) -> None:
    """AC1: a pyproject without a uv workspace table returns None."""
    _write_pyproject(tmp_path, '[project]\nname = "solo"\n')

    assert resolve_workspace_members(tmp_path) is None
