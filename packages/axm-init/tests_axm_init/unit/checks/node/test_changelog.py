"""Unit tests for the node changelog gold-standard check."""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.checks.node.changelog import check_changelog_automated


def _pkg(tmp_path: Path, data: dict[str, object]) -> None:
    """Write a package.json with *data*."""
    (tmp_path / "package.json").write_text(json.dumps(data))


def test_changeset_dir_passes(tmp_path: Path) -> None:
    """A .changeset directory counts as an automated changelog."""
    _pkg(tmp_path, {"name": "x"})
    (tmp_path / ".changeset").mkdir()
    assert check_changelog_automated(tmp_path).passed is True


def test_changesets_dependency_passes(tmp_path: Path) -> None:
    """A @changesets/cli devDependency counts as automated."""
    _pkg(tmp_path, {"name": "x", "devDependencies": {"@changesets/cli": "^2"}})
    assert check_changelog_automated(tmp_path).passed is True


def test_no_tooling_fails(tmp_path: Path) -> None:
    """No generator configured fails."""
    _pkg(tmp_path, {"name": "x"})
    assert check_changelog_automated(tmp_path).passed is False


def test_manual_changelog_without_tooling_fails(tmp_path: Path) -> None:
    """A hand-maintained CHANGELOG.md with no generator fails."""
    _pkg(tmp_path, {"name": "x"})
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
    result = check_changelog_automated(tmp_path)
    assert result.passed is False
    assert "manual" in result.message.lower()
