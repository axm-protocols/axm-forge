"""Split from ``test_identity_helpers.py``."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_git.core.identity import (
    GitIdentity,
    resolve_by_schedule,
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


@pytest.fixture()
def axm_workspace_path(axm_workspace_root: Path) -> Path:
    sub = axm_workspace_root / "axm-forge"
    sub.mkdir()
    return sub


@pytest.fixture()
def non_axm_path(tmp_path: Path) -> Path:
    other = tmp_path / "other-project"
    other.mkdir()
    return other


# ---------------------------------------------------------------------------
# resolve_by_schedule tests (AC3)
# ---------------------------------------------------------------------------


class TestResolveBySchedule:
    """Tests for resolve_by_schedule helper."""

    def test_axm_workspace_during_schedule_returns_profile(
        self, config, axm_workspace_path, work_identity
    ):
        # Monday 10:00 — within schedule
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_by_schedule(config, axm_workspace_path, now)
        assert result == work_identity

    def test_axm_workspace_outside_schedule_returns_none(
        self, config, axm_workspace_path
    ):
        # Monday 20:00 — outside schedule hours
        now = datetime(2026, 4, 6, 20, 0)  # Monday
        result = resolve_by_schedule(config, axm_workspace_path, now)
        assert result is None

    def test_axm_workspace_weekend_returns_none(self, config, axm_workspace_path):
        # Saturday 10:00 — weekend, not in schedule days
        now = datetime(2026, 4, 11, 10, 0)  # Saturday
        result = resolve_by_schedule(config, axm_workspace_path, now)
        assert result is None

    def test_non_axm_workspace_returns_none(self, config, non_axm_path, work_identity):
        # Monday 10:00 — within schedule but not AXM workspace
        now = datetime(2026, 4, 6, 10, 0)
        result = resolve_by_schedule(config, non_axm_path, now)
        assert result is None

    def test_schedule_with_unknown_profile_skips_rule(self, config, axm_workspace_path):
        # Rule references a profile that doesn't exist in config.profiles
        config.schedule.rules[0].profile = "deleted_profile"
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = resolve_by_schedule(config, axm_workspace_path, now)
        assert result is None
