from __future__ import annotations

import logging
from pathlib import Path

import pytest

from axm_ast.core.workspace import (
    _expand_workspace_members,
)


def test_expand_members_glob(tmp_path: Path) -> None:
    """Glob patterns are expanded to matching directory paths."""
    (tmp_path / "packages" / "pkg-a").mkdir(parents=True)
    (tmp_path / "packages" / "pkg-b").mkdir(parents=True)
    result = _expand_workspace_members(tmp_path, ["packages/*"])
    assert sorted(result) == ["packages/pkg-a", "packages/pkg-b"]


def test_expand_members_literal(tmp_path: Path) -> None:
    """Literal paths without glob chars are passed through."""
    (tmp_path / "mypackage").mkdir()
    result = _expand_workspace_members(tmp_path, ["mypackage"])
    assert result == ["mypackage"]


def test_expand_members_mixed(tmp_path: Path) -> None:
    """Mix of glob + literal entries all expand correctly."""
    (tmp_path / "packages" / "pkg-a").mkdir(parents=True)
    (tmp_path / "standalone").mkdir()
    result = _expand_workspace_members(tmp_path, ["packages/*", "standalone"])
    assert sorted(result) == ["packages/pkg-a", "standalone"]


def test_expand_members_no_match(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Glob with no matching dirs returns empty list and logs warning."""
    with caplog.at_level(logging.WARNING):
        result = _expand_workspace_members(tmp_path, ["nonexistent/*"])
    assert result == []
    assert any("nonexistent" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_expand_members_nested_globs(tmp_path: Path) -> None:
    """Nested glob patterns like 'packages/*/subpkg' expand correctly."""
    (tmp_path / "packages" / "group" / "subpkg").mkdir(parents=True)
    result = _expand_workspace_members(tmp_path, ["packages/*/subpkg"])
    assert result == ["packages/group/subpkg"]


def test_expand_members_no_glob_chars(tmp_path: Path) -> None:
    """Entry without glob chars is treated as literal path."""
    (tmp_path / "standalone-pkg").mkdir()
    result = _expand_workspace_members(tmp_path, ["standalone-pkg"])
    assert result == ["standalone-pkg"]


def test_expand_members_glob_matches_files_not_dirs(tmp_path: Path) -> None:
    """Files matching glob are filtered out; only directories kept."""
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "README.md").write_text("hello")
    (tmp_path / "packages" / "pkg-a").mkdir()
    result = _expand_workspace_members(tmp_path, ["packages/*"])
    assert result == ["packages/pkg-a"]
