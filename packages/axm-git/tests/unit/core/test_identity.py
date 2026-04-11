"""Unit tests for the identity module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from axm_git.core.identity import (
    GitIdentity,
    GitProfileConfig,
    author_args,
    load_config,
    resolve_identity,
)

AXM_WORKSPACE = Path(
    "/Users/gabriel/Documents/Code/python/axm-workspaces/axm-nexus/packages/axm-nexus"
)

VALID_TOML = """\
[default]
name = "Gabriel"
email = "gabriel@example.com"

[profiles.axiom]
name = "Axiom"
email = "axiom@axm-protocol.io"

[[schedule.rules]]
profile = "axiom"
days = ["mon", "tue", "wed", "thu", "fri"]
start = "09:00"
end = "18:00"
"""


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestGitIdentityModel:
    """Test GitIdentity pydantic model."""

    def test_git_identity_model(self) -> None:
        identity = GitIdentity(name="Axiom", email="axiom@axm-protocol.io")
        assert identity.name == "Axiom"
        assert identity.email == "axiom@axm-protocol.io"


# ---------------------------------------------------------------------------
# Config loading tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Test load_config function."""

    def test_load_config_valid(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text(VALID_TOML)
        config = load_config(cfg_file)
        assert config is not None
        assert isinstance(config, GitProfileConfig)
        assert config.default.name == "Gabriel"
        assert "axiom" in config.profiles
        assert len(config.schedule.rules) == 1

    def test_load_config_missing_file(self, tmp_path: Path) -> None:
        result = load_config(tmp_path / "nonexistent.toml")
        assert result is None

    def test_load_config_invalid_toml(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text("[[[invalid toml")
        result = load_config(cfg_file)
        assert result is None

    def test_load_config_empty_file(self, tmp_path: Path) -> None:
        """Config file exists but is 0 bytes."""
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text("")
        result = load_config(cfg_file)
        assert result is None


# ---------------------------------------------------------------------------
# resolve_identity tests
# ---------------------------------------------------------------------------


class TestResolveIdentity:
    """Test resolve_identity function."""

    @pytest.fixture()
    def config_path(self, tmp_path: Path) -> Path:
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text(VALID_TOML)
        return cfg_file

    def test_resolve_weekday_morning(self, config_path: Path) -> None:
        """Monday 10:00 + axm workspace -> axiom identity."""
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_identity(AXM_WORKSPACE, now=now, config_path=config_path)
        assert result is not None
        assert result.name == "Axiom"
        assert result.email == "axiom@axm-protocol.io"

    def test_resolve_weekday_evening(self, config_path: Path) -> None:
        """Monday 20:00 -> default identity (outside schedule)."""
        now = datetime(2026, 4, 6, 20, 0)  # Monday
        result = resolve_identity(AXM_WORKSPACE, now=now, config_path=config_path)
        assert result is not None
        assert result.name == "Gabriel"

    def test_resolve_weekend(self, config_path: Path) -> None:
        """Saturday 14:00 -> default identity."""
        now = datetime(2026, 4, 11, 14, 0)  # Saturday
        result = resolve_identity(AXM_WORKSPACE, now=now, config_path=config_path)
        assert result is not None
        assert result.name == "Gabriel"

    def test_resolve_non_axm_workspace(self, config_path: Path) -> None:
        """Monday 10:00 + non-axm path -> default (schedule ignored)."""
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_identity(
            Path("/tmp/other-repo"), now=now, config_path=config_path
        )
        assert result is not None
        assert result.name == "Gabriel"

    def test_resolve_profile_override(self, config_path: Path) -> None:
        """Override=default during schedule match -> default identity."""
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_identity(
            AXM_WORKSPACE,
            now=now,
            profile_override="default",
            config_path=config_path,
        )
        assert result is not None
        assert result.name == "Gabriel"

    def test_resolve_profile_override_axiom(self, config_path: Path) -> None:
        """Override=axiom on weekend -> axiom despite no schedule match."""
        now = datetime(2026, 4, 11, 14, 0)  # Saturday
        result = resolve_identity(
            AXM_WORKSPACE,
            now=now,
            profile_override="axiom",
            config_path=config_path,
        )
        assert result is not None
        assert result.name == "Axiom"

    def test_resolve_no_config(self, tmp_path: Path) -> None:
        """No config file -> None."""
        now = datetime(2026, 4, 6, 10, 0)
        result = resolve_identity(
            AXM_WORKSPACE,
            now=now,
            config_path=tmp_path / "missing.toml",
        )
        assert result is None

    def test_resolve_no_schedule_rules(self, tmp_path: Path) -> None:
        """Valid config but no schedule rules -> always default."""
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text(
            '[default]\nname = "Gabriel"\nemail = "gabriel@example.com"\n'
        )
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_identity(AXM_WORKSPACE, now=now, config_path=cfg_file)
        assert result is not None
        assert result.name == "Gabriel"

    def test_resolve_multiple_rules_first_wins(self, tmp_path: Path) -> None:
        """Two overlapping rules -> first matching rule wins."""
        toml_content = """\
[default]
name = "Gabriel"
email = "gabriel@example.com"

[profiles.axiom]
name = "Axiom"
email = "axiom@axm-protocol.io"

[profiles.other]
name = "Other"
email = "other@example.com"

[[schedule.rules]]
profile = "axiom"
days = ["mon"]
start = "09:00"
end = "18:00"

[[schedule.rules]]
profile = "other"
days = ["mon"]
start = "09:00"
end = "18:00"
"""
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text(toml_content)
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_identity(AXM_WORKSPACE, now=now, config_path=cfg_file)
        assert result is not None
        assert result.name == "Axiom"

    def test_resolve_unknown_profile_override(self, config_path: Path) -> None:
        """Override with nonexistent profile -> None."""
        now = datetime(2026, 4, 6, 10, 0)
        result = resolve_identity(
            AXM_WORKSPACE,
            now=now,
            profile_override="nonexistent",
            config_path=config_path,
        )
        assert result is None

    def test_resolve_symlink_workspace(self, config_path: Path, tmp_path: Path) -> None:
        """Symlink resolving to $W/axm-* -> schedule applies."""
        symlink = tmp_path / "linked-repo"
        symlink.symlink_to(AXM_WORKSPACE)
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_identity(symlink, now=now, config_path=config_path)
        assert result is not None
        assert result.name == "Axiom"


# ---------------------------------------------------------------------------
# Schedule boundary tests
# ---------------------------------------------------------------------------


class TestScheduleBoundaries:
    """Test schedule matching edge cases."""

    @pytest.fixture()
    def config_path(self, tmp_path: Path) -> Path:
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text(VALID_TOML)
        return cfg_file

    def test_matches_schedule_boundary_start(self, config_path: Path) -> None:
        """Monday 09:00 exactly -> matches (inclusive)."""
        now = datetime(2026, 4, 6, 9, 0)  # Monday 09:00
        result = resolve_identity(AXM_WORKSPACE, now=now, config_path=config_path)
        assert result is not None
        assert result.name == "Axiom"

    def test_matches_schedule_boundary_end(self, config_path: Path) -> None:
        """Monday 18:00 exactly -> does not match (exclusive)."""
        now = datetime(2026, 4, 6, 18, 0)  # Monday 18:00
        result = resolve_identity(AXM_WORKSPACE, now=now, config_path=config_path)
        assert result is not None
        assert result.name == "Gabriel"


# ---------------------------------------------------------------------------
# Workspace detection tests
# ---------------------------------------------------------------------------


class TestIsAxmWorkspace:
    """Test _is_axm_workspace via resolve_identity behavior."""

    @pytest.fixture()
    def config_path(self, tmp_path: Path) -> Path:
        cfg_file = tmp_path / "git-profiles.toml"
        cfg_file.write_text(VALID_TOML)
        return cfg_file

    def test_is_axm_workspace_true(self, config_path: Path) -> None:
        """Path under $W/axm-nexus/... -> schedule applies."""
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_identity(AXM_WORKSPACE, now=now, config_path=config_path)
        assert result is not None
        assert result.name == "Axiom"

    def test_is_axm_workspace_false(self, config_path: Path) -> None:
        """Path under /tmp/other -> schedule ignored."""
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_identity(Path("/tmp/other"), now=now, config_path=config_path)
        assert result is not None
        assert result.name == "Gabriel"


# ---------------------------------------------------------------------------
# author_args tests
# ---------------------------------------------------------------------------


class TestAuthorArgs:
    """Test author_args helper."""

    def test_author_args_with_identity(self) -> None:
        identity = GitIdentity(name="Axiom", email="axiom@axm-protocol.io")
        result = author_args(identity)
        assert result == ["--author", "Axiom <axiom@axm-protocol.io>"]

    def test_author_args_none(self) -> None:
        result = author_args(None)
        assert result == []
