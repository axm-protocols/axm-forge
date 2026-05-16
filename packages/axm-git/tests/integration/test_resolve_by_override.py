"""Split from ``test_identity_helpers.py``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_git.core.identity import (
    GitIdentity,
    _resolve_by_override,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def default_identity() -> GitIdentity:
    return GitIdentity(name="Default User", email="default@example.com")


@pytest.fixture()
def work_identity() -> GitIdentity:
    return GitIdentity(name="Work User", email="work@example.com")


@pytest.fixture()
def personal_identity() -> GitIdentity:
    return GitIdentity(name="Personal User", email="personal@example.com")


@pytest.fixture()
def axm_workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspaces"
    root.mkdir()
    return root


@pytest.fixture()
def config(
    default_identity: GitIdentity,
    work_identity: GitIdentity,
    personal_identity: GitIdentity,
    axm_workspace_root: Path,
) -> MagicMock:
    """Minimal config mock with default + two named profiles + one schedule rule."""
    rule = MagicMock()
    rule.days = ["mon", "tue", "wed", "thu", "fri"]
    rule.start = "09:00"
    rule.end = "18:00"
    rule.profile = "work"

    cfg = MagicMock()
    cfg.default = default_identity
    cfg.profiles = {
        "work": work_identity,
        "personal": personal_identity,
    }
    cfg.schedule.rules = [rule]
    cfg.workspace_paths = [axm_workspace_root]
    cfg.timezone = "Europe/Paris"
    return cfg


# ---------------------------------------------------------------------------
# _resolve_by_override tests (AC2)
# ---------------------------------------------------------------------------


class TestResolveByOverride:
    """Tests for _resolve_by_override helper."""

    def test_override_default_returns_default_identity(self, config, default_identity):
        result = _resolve_by_override(config, "default")
        assert result == default_identity

    def test_override_named_profile_returns_profile(self, config, work_identity):
        result = _resolve_by_override(config, "work")
        assert result == work_identity

    def test_override_another_named_profile(self, config, personal_identity):
        result = _resolve_by_override(config, "personal")
        assert result == personal_identity

    def test_override_unknown_profile_returns_none(self, config):
        result = _resolve_by_override(config, "nonexistent")
        assert result is None

    def test_override_none_returns_none(self, config):
        """When profile_override is None, helper should return None (no match)."""
        result = _resolve_by_override(config, None)
        assert result is None
