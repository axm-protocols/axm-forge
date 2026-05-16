"""Split from ``test_identity.py``."""

from __future__ import annotations

import logging as _logging_axm1710
from pathlib import Path
from typing import Any

import pytest

from axm_git.core.identity import load_config

pytestmark = pytest.mark.integration


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
