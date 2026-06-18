from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot.uv import resolve_workspace

pytestmark = pytest.mark.integration


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_resolves_members_with_pyproject(tmp_path: Path) -> None:
    """AC2, AC3: globbed members containing a pyproject are resolved + sorted."""
    _write(
        tmp_path / "pyproject.toml",
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n',
    )
    _write(
        tmp_path / "packages" / "beta" / "pyproject.toml", '[project]\nname = "beta"\n'
    )
    _write(
        tmp_path / "packages" / "alpha" / "pyproject.toml",
        '[project]\nname = "alpha"\n',
    )

    resolved = resolve_workspace(tmp_path)

    assert resolved is not None
    assert [m.name for m in resolved.members] == ["alpha", "beta"]
    assert resolved.members[0].path == (tmp_path / "packages" / "alpha").resolve()
    assert resolved.members[1].path == (tmp_path / "packages" / "beta").resolve()


def test_applies_exclude(tmp_path: Path) -> None:
    """AC2: exclude globs subtract members (regression on the audit bug)."""
    _write(
        tmp_path / "pyproject.toml",
        '[tool.uv.workspace]\nmembers = ["packages/*"]\nexclude = ["packages/skip"]\n',
    )
    _write(
        tmp_path / "packages" / "keep" / "pyproject.toml", '[project]\nname = "keep"\n'
    )
    _write(
        tmp_path / "packages" / "skip" / "pyproject.toml", '[project]\nname = "skip"\n'
    )

    resolved = resolve_workspace(tmp_path)

    assert resolved is not None
    assert [m.name for m in resolved.members] == ["keep"]


def test_skips_dirs_without_pyproject(tmp_path: Path) -> None:
    """AC2: a glob-matched dir without pyproject is not listed (require_pyproject)."""
    _write(
        tmp_path / "pyproject.toml",
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n',
    )
    _write(
        tmp_path / "packages" / "real" / "pyproject.toml", '[project]\nname = "real"\n'
    )
    (tmp_path / "packages" / "empty").mkdir(parents=True, exist_ok=True)

    resolved = resolve_workspace(tmp_path)

    assert resolved is not None
    assert [m.name for m in resolved.members] == ["real"]


@pytest.mark.parametrize(
    "pyproject_text",
    [
        pytest.param('[project]\nname = "solo"\n', id="no-uv-workspace-table"),
        pytest.param("[tool.uv.workspace\nmembers = [\n", id="malformed-toml"),
    ],
)
def test_returns_none_when_not_a_workspace(tmp_path: Path, pyproject_text: str) -> None:
    """AC2, AC5: a pyproject without [tool.uv.workspace] and an invalid TOML
    pyproject both yield None without raising."""
    _write(tmp_path / "pyproject.toml", pyproject_text)

    assert resolve_workspace(tmp_path) is None
