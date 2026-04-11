"""Tests for extracted identity helpers: _resolve_by_override, _resolve_by_schedule.

These tests cover AC2, AC3, and the edge cases from the test spec.
The existing 15 tests in test_identity.py are left untouched (AC4).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_git.core.identity import (
    GitIdentity,
    _resolve_by_override,
    _resolve_by_schedule,
    resolve_identity,
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
def config(default_identity, work_identity, personal_identity):
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
    return cfg


@pytest.fixture()
def axm_workspace_path() -> Path:
    return Path("/Users/gabriel/Documents/Code/python/axm-workspaces/axm-forge")


@pytest.fixture()
def non_axm_path() -> Path:
    return Path("/Users/gabriel/Documents/other-project")


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


# ---------------------------------------------------------------------------
# _resolve_by_schedule tests (AC3)
# ---------------------------------------------------------------------------


class TestResolveBySchedule:
    """Tests for _resolve_by_schedule helper."""

    def test_axm_workspace_during_schedule_returns_profile(
        self, config, axm_workspace_path, work_identity
    ):
        # Monday 10:00 — within schedule
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = _resolve_by_schedule(config, axm_workspace_path, now)
        assert result == work_identity

    def test_axm_workspace_outside_schedule_returns_none(
        self, config, axm_workspace_path
    ):
        # Monday 20:00 — outside schedule hours
        now = datetime(2026, 4, 6, 20, 0)  # Monday
        result = _resolve_by_schedule(config, axm_workspace_path, now)
        assert result is None

    def test_axm_workspace_weekend_returns_none(self, config, axm_workspace_path):
        # Saturday 10:00 — weekend, not in schedule days
        now = datetime(2026, 4, 11, 10, 0)  # Saturday
        result = _resolve_by_schedule(config, axm_workspace_path, now)
        assert result is None

    def test_non_axm_workspace_returns_none(self, config, non_axm_path, work_identity):
        # Monday 10:00 — within schedule but not AXM workspace
        now = datetime(2026, 4, 6, 10, 0)
        result = _resolve_by_schedule(config, non_axm_path, now)
        assert result is None

    def test_schedule_with_unknown_profile_skips_rule(self, config, axm_workspace_path):
        # Rule references a profile that doesn't exist in config.profiles
        config.schedule.rules[0].profile = "deleted_profile"
        now = datetime(2026, 4, 6, 10, 0)  # Monday
        result = _resolve_by_schedule(config, axm_workspace_path, now)
        assert result is None


# ---------------------------------------------------------------------------
# Edge cases on resolve_identity (test_spec)
# ---------------------------------------------------------------------------


class TestResolveIdentityEdgeCases:
    """Edge cases from test spec — exercised through the public function."""

    def test_unknown_override_profile_returns_none(self, config, monkeypatch):
        monkeypatch.setattr("axm_git.core.identity.load_config", lambda _: config)
        result = resolve_identity(
            Path("/any"),
            profile_override="nonexistent",
        )
        assert result is None

    def test_no_config_file_returns_none(self, monkeypatch):
        monkeypatch.setattr("axm_git.core.identity.load_config", lambda _: None)
        result = resolve_identity(Path("/any"))
        assert result is None

    def test_non_axm_workspace_falls_through_to_default(
        self, config, default_identity, non_axm_path, monkeypatch
    ):
        monkeypatch.setattr("axm_git.core.identity.load_config", lambda _: config)
        result = resolve_identity(non_axm_path)
        assert result == default_identity
