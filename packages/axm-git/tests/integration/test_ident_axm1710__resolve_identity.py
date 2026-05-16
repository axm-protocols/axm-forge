"""Split from ``test_identity.py``."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo as _ZoneInfo_axm1710

import pytest

import axm_git.core.identity as _ident_axm1710
from axm_git.core.identity import (
    GitProfileConfig,
    resolve_identity,
)

pytestmark = pytest.mark.integration


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
    assert result.name == "Work"
