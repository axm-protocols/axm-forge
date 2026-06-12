"""Registering a new member adds a per-package Dependabot entry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from axm_init.adapters.workspace_patcher import patch_dependabot


class TestDependabotGetsMemberEntry:
    """patch_dependabot adds a per-package uv update block."""

    def test_adds_member_entry(self, workspace_root: Path) -> None:
        patch_dependabot(workspace_root, "my-lib")

        content = (workspace_root / ".github" / "dependabot.yml").read_text()
        assert "directory: /packages/my-lib" in content

    def test_idempotent(self, workspace_root: Path) -> None:
        patch_dependabot(workspace_root, "my-lib")
        content1 = (workspace_root / ".github" / "dependabot.yml").read_text()
        patch_dependabot(workspace_root, "my-lib")
        content2 = (workspace_root / ".github" / "dependabot.yml").read_text()
        assert content1 == content2

    def test_missing_dependabot_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            patch_dependabot(tmp_path, "my-lib")

    def test_entry_before_github_actions(self, workspace_root: Path) -> None:
        """The per-package block lands before the github-actions entry."""
        patch_dependabot(workspace_root, "my-lib")
        content = (workspace_root / ".github" / "dependabot.yml").read_text()
        member_pos = content.index("directory: /packages/my-lib")
        gha_pos = content.index("package-ecosystem: github-actions")
        assert member_pos < gha_pos

    def test_appends_when_no_github_actions_anchor(self, tmp_path: Path) -> None:
        """Without a github-actions entry, the block is appended at the end."""
        dependabot = tmp_path / ".github" / "dependabot.yml"
        dependabot.parent.mkdir(parents=True, exist_ok=True)
        dependabot.write_text(
            "version: 2\nupdates:\n"
            "  - package-ecosystem: uv\n    directory: /\n"
            "    schedule:\n      interval: weekly\n"
        )

        patch_dependabot(tmp_path, "my-lib")

        content = dependabot.read_text()
        assert "directory: /packages/my-lib" in content


# ─ YAML safety ───────────────────────────────────────────────────────────────


def test_patch_dependabot_keeps_yaml_parseable(workspace_root: Path) -> None:
    """The result is still a valid Dependabot config with the new entry."""
    patch_dependabot(workspace_root, "my-lib")
    parsed = yaml.safe_load((workspace_root / ".github" / "dependabot.yml").read_text())
    assert isinstance(parsed, dict)
    dirs = [u["directory"] for u in parsed["updates"] if u["package-ecosystem"] == "uv"]
    assert "/" in dirs
    assert "/packages/my-lib" in dirs


def test_patch_dependabot_member_group_scoped(workspace_root: Path) -> None:
    """The member entry groups under its own name with a wildcard pattern."""
    patch_dependabot(workspace_root, "my-lib")
    parsed = yaml.safe_load((workspace_root / ".github" / "dependabot.yml").read_text())
    entry = next(
        u for u in parsed["updates"] if u.get("directory") == "/packages/my-lib"
    )
    assert entry["groups"] == {"my-lib": {"patterns": ["*"]}}
