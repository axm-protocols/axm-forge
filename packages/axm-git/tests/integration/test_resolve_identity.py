"""Integration test: real TOML file + resolve_identity end-to-end.

Also merges edge-case tests from former ``test_identity_helpers.py``
and resolve_identity-only tests split from former ``test_identity.py``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from axm_git.core.identity import GitIdentity, resolve_identity

pytestmark = pytest.mark.integration

AXM_WORKSPACE_ROOT = Path("/tmp/axm-workspaces-test-root")
AXM_WORKSPACE = AXM_WORKSPACE_ROOT / "axm-nexus" / "packages" / "axm-nexus"

VALID_TOML = f"""\
workspace_paths = ["{AXM_WORKSPACE_ROOT}"]

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


def _write_toml(
    path: Path,
    *,
    workspace_paths: list[Path],
    timezone: str,
) -> None:
    joined = ", ".join(f'"{p}"' for p in workspace_paths)
    path.write_text(
        f"""\
timezone = "{timezone}"
workspace_paths = [{joined}]

[default]
name = "Default"
email = "default@example.com"

[profiles.work]
name = "Work User"
email = "work@example.com"

[[schedule.rules]]
days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
start = "00:00"
end = "23:59"
profile = "work"
"""
    )


def test_resolve_identity_reads_real_toml_file(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    inside = workspace_root / "project"
    inside.mkdir()
    outside = tmp_path / "other"
    outside.mkdir()

    cfg_path = tmp_path / "git-profiles.toml"
    _write_toml(
        cfg_path,
        workspace_paths=[workspace_root],
        timezone="Europe/Paris",
    )

    now = datetime(2026, 1, 5, 12, 0, tzinfo=ZoneInfo("Europe/Paris"))

    inside_result = resolve_identity(inside, now=now, config_path=cfg_path)
    assert inside_result is not None
    assert inside_result.name == "Work User"

    outside_result = resolve_identity(outside, now=now, config_path=cfg_path)
    assert outside_result is not None
    assert outside_result.name == "Default"

    missing_cfg = tmp_path / "absent.toml"
    assert resolve_identity(inside, now=now, config_path=missing_cfg) is None


# ---------------------------------------------------------------------------
# Edge cases merged from former test_identity_helpers.py
# ---------------------------------------------------------------------------


@pytest.fixture()
def _edge_default_identity() -> GitIdentity:
    return GitIdentity(name="Default User", email="default@example.com")


@pytest.fixture()
def _edge_work_identity() -> GitIdentity:
    return GitIdentity(name="Work User", email="work@example.com")


@pytest.fixture()
def _edge_personal_identity() -> GitIdentity:
    return GitIdentity(name="Personal User", email="personal@example.com")


@pytest.fixture()
def _edge_axm_workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspaces"
    root.mkdir()
    return root


@pytest.fixture()
def _edge_config(
    _edge_default_identity: GitIdentity,
    _edge_work_identity: GitIdentity,
    _edge_personal_identity: GitIdentity,
    _edge_axm_workspace_root: Path,
) -> MagicMock:
    """Minimal config mock with default + two named profiles + one schedule rule."""
    rule = MagicMock()
    rule.days = ["mon", "tue", "wed", "thu", "fri"]
    rule.start = "09:00"
    rule.end = "18:00"
    rule.profile = "work"

    cfg = MagicMock()
    cfg.default = _edge_default_identity
    cfg.profiles = {
        "work": _edge_work_identity,
        "personal": _edge_personal_identity,
    }
    cfg.schedule.rules = [rule]
    cfg.workspace_paths = [_edge_axm_workspace_root]
    cfg.timezone = "Europe/Paris"
    return cfg


@pytest.fixture()
def _edge_non_axm_path(tmp_path: Path) -> Path:
    other = tmp_path / "other-project"
    other.mkdir()
    return other


class TestResolveIdentityEdgeCases:
    """Edge cases from test spec — exercised through the public function."""

    def test_unknown_override_profile_returns_none(self, _edge_config, monkeypatch):
        monkeypatch.setattr("axm_git.core.identity.load_config", lambda _: _edge_config)
        result = resolve_identity(
            Path("/any"),
            profile_override="nonexistent",
        )
        assert result is None

    def test_non_axm_workspace_falls_through_to_default(
        self,
        _edge_config,
        _edge_default_identity,
        _edge_non_axm_path,
        monkeypatch,
    ):
        monkeypatch.setattr("axm_git.core.identity.load_config", lambda _: _edge_config)
        result = resolve_identity(_edge_non_axm_path)
        assert result == _edge_default_identity


# ---------------------------------------------------------------------------
# Tests merged from former ``test_identity.py`` (resolve_identity alone)
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

    @pytest.mark.parametrize(
        ("now", "profile_override", "expected_name"),
        [
            pytest.param(
                datetime(2026, 4, 6, 10, 0),
                "default",
                "Gabriel",
                id="override_default_during_schedule_match",
            ),
            pytest.param(
                datetime(2026, 4, 11, 14, 0),
                "axiom",
                "Axiom",
                id="override_axiom_on_weekend",
            ),
        ],
    )
    def test_resolve_profile_override(
        self,
        config_path: Path,
        now: datetime,
        profile_override: str,
        expected_name: str,
    ) -> None:
        """profile_override beats schedule resolution in both directions."""
        result = resolve_identity(
            AXM_WORKSPACE,
            now=now,
            profile_override=profile_override,
            config_path=config_path,
        )
        assert result is not None
        assert result.name == expected_name

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
        toml_content = f"""\
workspace_paths = ["{AXM_WORKSPACE_ROOT}"]

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
