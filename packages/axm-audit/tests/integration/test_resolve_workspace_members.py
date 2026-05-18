from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.dependencies import (
    resolve_workspace_members,
)


def _write_pyproject(path: Path, content: str = "") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(content)


def _workspace_toml(*member_patterns: str) -> str:
    members = ", ".join(f'"{p}"' for p in member_patterns)
    return f"[tool.uv.workspace]\nmembers = [{members}]\n"


# ---------------------------------------------------------------------------
# _resolve_workspace_members — unit tests
# ---------------------------------------------------------------------------


class TestResolveWorkspaceMembers:
    @pytest.mark.parametrize(
        ("member_patterns", "package_paths", "expected_names"),
        [
            pytest.param(
                ("packages/*",),
                ("packages/pkg-a", "packages/pkg-b"),
                ["pkg-a", "pkg-b"],
                id="single_pattern",
            ),
            pytest.param(
                ("packages/*", "libs/*"),
                ("packages/pkg-a", "libs/lib-x"),
                ["lib-x", "pkg-a"],
                id="multiple_patterns",
            ),
        ],
    )
    def test_resolve_returns_member_names(
        self,
        tmp_path: Path,
        member_patterns: tuple[str, ...],
        package_paths: tuple[str, ...],
        expected_names: list[str],
    ) -> None:
        """Workspace globs resolve to sub-dirs with pyproject.toml."""
        _write_pyproject(tmp_path, _workspace_toml(*member_patterns))
        for pkg in package_paths:
            _write_pyproject(tmp_path / pkg)

        result = resolve_workspace_members(tmp_path)

        assert result is not None
        assert sorted(p.name for p in result) == expected_names

    def test_resolve_workspace_members_no_workspace(self, tmp_path: Path) -> None:
        """Non-workspace pyproject returns None."""
        _write_pyproject(tmp_path, '[project]\nname = "solo"\n')

        result = resolve_workspace_members(tmp_path)

        assert result is None

    def test_resolve_workspace_members_empty_glob(self, tmp_path: Path) -> None:
        """Workspace glob matching no directories returns empty list."""
        _write_pyproject(tmp_path, _workspace_toml("packages/*"))
        (tmp_path / "packages").mkdir()

        result = resolve_workspace_members(tmp_path)

        assert result == []

    def test_resolve_workspace_members_skips_no_pyproject(self, tmp_path: Path) -> None:
        """Dirs without pyproject.toml are silently skipped."""
        _write_pyproject(tmp_path, _workspace_toml("packages/*"))
        _write_pyproject(tmp_path / "packages" / "has-pyproject")
        (tmp_path / "packages" / "no-pyproject").mkdir(parents=True)

        result = resolve_workspace_members(tmp_path)

        assert result is not None
        assert len(result) == 1
        assert result[0].name == "has-pyproject"
