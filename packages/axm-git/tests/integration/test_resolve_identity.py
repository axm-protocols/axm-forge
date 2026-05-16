"""Integration test: real TOML file + resolve_identity end-to-end.

Also merges edge-case tests from former ``test_identity_helpers.py``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from axm_git.core.identity import GitIdentity, resolve_identity

pytestmark = pytest.mark.integration


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
