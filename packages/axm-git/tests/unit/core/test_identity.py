"""Unit tests for the identity module."""

from __future__ import annotations

import inspect as _inspect_axm1710
import logging as _logging_axm1710
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo as _ZoneInfo_axm1710

import pytest

import axm_git.core.identity as _ident_axm1710
from axm_git.core.identity import (
    GitIdentity,
    GitProfileConfig,
    author_args,
    load_config,
    resolve_identity,
)

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


# ---------------------------------------------------------------------------
# axm-1710 — workspace_paths + tz-aware schedule + load_config logging
# ---------------------------------------------------------------------------


def _build_config_axm1710(
    *,
    workspace_paths: list[Path] | None = None,
    timezone: str | None = None,
    schedule_rules: list[dict[str, Any]] | None = None,
    profiles: dict[str, dict[str, str]] | None = None,
) -> GitProfileConfig:
    payload: dict[str, Any] = {
        "default": {"name": "Default", "email": "default@example.com"},
        "profiles": profiles or {},
        "schedule": {"rules": schedule_rules or []},
    }
    if workspace_paths is not None:
        payload["workspace_paths"] = [str(p) for p in workspace_paths]
    if timezone is not None:
        payload["timezone"] = timezone
    return GitProfileConfig.model_validate(payload)


def _write_toml_axm1710(
    path: Path,
    *,
    workspace_paths: list[Path] | None = None,
    timezone: str | None = None,
    schedule_rules: list[dict[str, Any]] | None = None,
    profiles: dict[str, dict[str, str]] | None = None,
) -> None:
    lines: list[str] = []
    if timezone is not None:
        lines.append(f'timezone = "{timezone}"')
    if workspace_paths is not None:
        joined = ", ".join(f'"{p}"' for p in workspace_paths)
        lines.append(f"workspace_paths = [{joined}]")
    lines.extend(
        [
            "[default]",
            'name = "Default"',
            'email = "default@example.com"',
        ]
    )
    if profiles:
        for pname, pdata in profiles.items():
            lines.append(f"[profiles.{pname}]")
            lines.append(f'name = "{pdata["name"]}"')
            lines.append(f'email = "{pdata["email"]}"')
    if schedule_rules:
        for rule in schedule_rules:
            lines.append("[[schedule.rules]]")
            days = ", ".join(f'"{d}"' for d in rule["days"])
            lines.append(f"days = [{days}]")
            lines.append(f'start = "{rule["start"]}"')
            lines.append(f'end = "{rule["end"]}"')
            lines.append(f'profile = "{rule["profile"]}"')
    path.write_text("\n".join(lines) + "\n")


_WORK_PROFILE = {"work": {"name": "Work", "email": "work@example.com"}}
_ANYTIME_RULE = [
    {
        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "start": "00:00",
        "end": "23:59",
        "profile": "work",
    }
]


# AC1


def test_resolve_identity_with_workspace_path_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config_axm1710(
        workspace_paths=[tmp_path],
        profiles=_WORK_PROFILE,
        schedule_rules=_ANYTIME_RULE,
    )
    monkeypatch.setattr(_ident_axm1710, "load_config", lambda _p=None: config)
    sub = tmp_path / "proj"
    sub.mkdir()
    result = resolve_identity(sub)
    assert result is not None
    assert result.name == "Work"


def test_resolve_identity_outside_workspace_paths_falls_through_to_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inside_root = tmp_path / "inside"
    inside_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    config = _build_config_axm1710(
        workspace_paths=[inside_root],
        profiles=_WORK_PROFILE,
        schedule_rules=_ANYTIME_RULE,
    )
    monkeypatch.setattr(_ident_axm1710, "load_config", lambda _p=None: config)
    result = resolve_identity(outside)
    assert result == config.default


def test_resolve_identity_empty_workspace_paths_never_applies_schedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config_axm1710(
        workspace_paths=[],
        profiles=_WORK_PROFILE,
        schedule_rules=_ANYTIME_RULE,
    )
    monkeypatch.setattr(_ident_axm1710, "load_config", lambda _p=None: config)
    result = resolve_identity(tmp_path)
    assert result == config.default


def test_resolve_identity_multiple_workspace_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    config = _build_config_axm1710(
        workspace_paths=[root_a, root_b],
        profiles=_WORK_PROFILE,
        schedule_rules=_ANYTIME_RULE,
    )
    monkeypatch.setattr(_ident_axm1710, "load_config", lambda _p=None: config)
    inside_b = root_b / "proj"
    inside_b.mkdir()
    result = resolve_identity(inside_b)
    assert result is not None
    assert result.name == "Work"


def test_resolve_identity_workspace_paths_resolves_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    real_sub = real_root / "sub"
    real_sub.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real_root)
    config = _build_config_axm1710(
        workspace_paths=[real_root],
        profiles=_WORK_PROFILE,
        schedule_rules=_ANYTIME_RULE,
    )
    monkeypatch.setattr(_ident_axm1710, "load_config", lambda _p=None: config)
    result = resolve_identity(link / "sub")
    assert result is not None
    assert result.name == "Work"


# AC2


def test_no_hardcoded_workspace_prefix_in_module() -> None:
    src = _inspect_axm1710.getsource(_ident_axm1710)
    assert "/Users/" not in src
    assert "_AXM_WORKSPACE_PREFIX" not in src


# AC3


def test_resolve_identity_uses_configured_timezone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config_axm1710(
        workspace_paths=[tmp_path],
        timezone="America/New_York",
        profiles=_WORK_PROFILE,
        schedule_rules=[
            {
                "days": ["mon", "tue", "wed", "thu", "fri"],
                "start": "09:00",
                "end": "18:00",
                "profile": "work",
            }
        ],
    )
    monkeypatch.setattr(_ident_axm1710, "load_config", lambda _p=None: config)

    # 2026-01-05 (Mon) 14:00 NY -> within NY 9-18 window -> work profile.
    ny_now = datetime(2026, 1, 5, 14, 0, tzinfo=_ZoneInfo_axm1710("America/New_York"))
    result = resolve_identity(tmp_path, now=ny_now)
    assert result is not None and result.name == "Work"

    # 2026-01-05 (Mon) 14:00 Paris == 08:00 NY -> outside NY 9-18 -> default.
    paris_now = datetime(2026, 1, 5, 14, 0, tzinfo=_ZoneInfo_axm1710("Europe/Paris"))
    result2 = resolve_identity(tmp_path, now=paris_now)
    assert result2 == config.default


def test_resolve_identity_default_timezone_is_europe_paris() -> None:
    config = _build_config_axm1710()
    assert config.timezone == "Europe/Paris"


def test_matches_schedule_accepts_tz_aware_datetime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _build_config_axm1710(
        workspace_paths=[tmp_path],
        profiles=_WORK_PROFILE,
        schedule_rules=_ANYTIME_RULE,
    )
    monkeypatch.setattr(_ident_axm1710, "load_config", lambda _p=None: config)
    tz_aware = datetime(2026, 1, 5, 12, 0, tzinfo=_ZoneInfo_axm1710("Europe/Paris"))
    result = resolve_identity(tmp_path, now=tz_aware)
    assert result is not None


# AC4


def test_load_config_warns_on_malformed_toml(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = = not valid toml [[[")
    with caplog.at_level(_logging_axm1710.WARNING, logger="axm_git.core.identity"):
        result = load_config(bad)
    assert result is None
    assert len(caplog.records) >= 1
    assert any(str(bad) in rec.getMessage() for rec in caplog.records)


def test_load_config_warns_on_invalid_schema(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text('[some_section]\nkey = "value"\n')  # missing 'default'
    with caplog.at_level(_logging_axm1710.WARNING, logger="axm_git.core.identity"):
        result = load_config(bad)
    assert result is None
    assert len(caplog.records) >= 1


def test_load_config_silent_on_missing_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = tmp_path / "does_not_exist.toml"
    with caplog.at_level(_logging_axm1710.WARNING, logger="axm_git.core.identity"):
        result = load_config(missing)
    assert result is None
    assert len(caplog.records) == 0


def test_load_config_silent_on_empty_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    empty = tmp_path / "empty.toml"
    empty.write_text("")
    with caplog.at_level(_logging_axm1710.WARNING, logger="axm_git.core.identity"):
        result = load_config(empty)
    assert result is None
    assert len(caplog.records) == 0


# AC5


def test_load_config_warns_when_schedule_set_but_workspace_paths_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = tmp_path / "cfg.toml"
    _write_toml_axm1710(
        cfg,
        workspace_paths=[],
        profiles=_WORK_PROFILE,
        schedule_rules=[
            {"days": ["mon"], "start": "09:00", "end": "18:00", "profile": "work"}
        ],
    )
    with caplog.at_level(_logging_axm1710.WARNING, logger="axm_git.core.identity"):
        result = load_config(cfg)
    assert result is not None
    inert_msgs = [
        rec.getMessage().lower()
        for rec in caplog.records
        if "inert" in rec.getMessage().lower()
        or "workspace_paths" in rec.getMessage().lower()
        or "schedule" in rec.getMessage().lower()
    ]
    assert len(inert_msgs) >= 1


def test_load_config_no_warning_when_workspace_paths_set(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg = tmp_path / "cfg.toml"
    _write_toml_axm1710(
        cfg,
        workspace_paths=[tmp_path],
        profiles=_WORK_PROFILE,
        schedule_rules=[
            {"days": ["mon"], "start": "09:00", "end": "18:00", "profile": "work"}
        ],
    )
    with caplog.at_level(_logging_axm1710.WARNING, logger="axm_git.core.identity"):
        result = load_config(cfg)
    assert result is not None
    inert_warnings = [
        rec for rec in caplog.records if "inert" in rec.getMessage().lower()
    ]
    assert len(inert_warnings) == 0
