"""Integration test: real TOML file + resolve_identity end-to-end."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from axm_git.core.identity import resolve_identity

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
