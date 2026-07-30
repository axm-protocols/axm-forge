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

    @pytest.mark.parametrize(
        ("now", "use_axm_path", "mutate_profile"),
        [
            pytest.param(
                datetime(2026, 4, 6, 20, 0),  # Monday 20:00
                True,
                False,
                id="axm_outside_schedule",
            ),
            pytest.param(
                datetime(2026, 4, 11, 10, 0),  # Saturday 10:00
                True,
                False,
                id="axm_weekend",
            ),
            pytest.param(
                datetime(2026, 4, 6, 10, 0),  # Monday 10:00
                False,
                False,
                id="non_axm_workspace",
            ),
            pytest.param(
                datetime(2026, 4, 6, 10, 0),  # Monday 10:00
                True,
                True,
                id="unknown_profile",
            ),
        ],
    )
    def test_returns_none(
        self,
        config,
        axm_workspace_path,
        non_axm_path,
        now,
        use_axm_path,
        mutate_profile,
    ):
        if mutate_profile:
            config.schedule.rules[0].profile = "deleted_profile"
        path = axm_workspace_path if use_axm_path else non_axm_path
        result = resolve_by_schedule(config, path, now)
        assert result is None
