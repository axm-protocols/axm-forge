"""Split from ``test_identity_helpers.py``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_git.core.identity import (
    GitIdentity,
    resolve_by_override,
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
# resolve_by_override tests (AC2)
# ---------------------------------------------------------------------------


class TestResolveByOverride:
    """Tests for resolve_by_override helper."""

    @pytest.mark.parametrize(
        ("override", "expected_fixture"),
        [
            pytest.param(
                "default", "default_identity", id="default_returns_default_identity"
            ),
            pytest.param("work", "work_identity", id="named_profile_returns_profile"),
            pytest.param("personal", "personal_identity", id="another_named_profile"),
        ],
    )
    def test_override_returns_matching_identity(
        self,
        config: MagicMock,
        request: pytest.FixtureRequest,
        override: str,
        expected_fixture: str,
    ) -> None:
        expected = request.getfixturevalue(expected_fixture)
        result = resolve_by_override(config, override)
        assert result == expected

    @pytest.mark.parametrize(
        "override",
        [
            pytest.param("nonexistent", id="unknown_profile_returns_none"),
            pytest.param(None, id="none_returns_none"),
        ],
    )
    def test_override_returns_none_when_no_match(
        self, config: MagicMock, override: str | None
    ) -> None:
        result = resolve_by_override(config, override)
        assert result is None
