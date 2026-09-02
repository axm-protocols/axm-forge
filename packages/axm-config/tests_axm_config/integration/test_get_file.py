from __future__ import annotations

from pathlib import Path

import pytest

import axm_config
from axm_config import set_

pytestmark = pytest.mark.integration


def test_file_only_resolution_ignores_environment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: get_file returns the file value despite an environment override."""
    set_("demo", "token", "persisted")
    monkeypatch.setenv("AXM_DEMO_TOKEN", "environment")

    assert axm_config.get_file("demo", "token", default="fallback") == "persisted"


@pytest.mark.parametrize("file_state", ("absent_home", "absent_file", "malformed"))
def test_file_only_resolution_degrades_to_default(file_state: str) -> None:
    """AC3: get_file defaults for absent AXM state and malformed TOML."""
    axm_home = Path.home() / ".axm"
    if file_state == "absent_file":
        axm_home.mkdir(parents=True)
    elif file_state == "malformed":
        axm_home.mkdir(parents=True)
        (axm_home / "config.toml").write_text(
            "[demo\ntoken = 'broken'",
            encoding="utf-8",
        )

    assert axm_config.get_file("demo", "token", default="fallback") == "fallback"


def test_dev_profile_store_wins_over_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: get_file reads the selected profile instead of production."""
    axm_home = Path.home() / ".axm"
    production_path = axm_home / "config.toml"
    profile_path = axm_home / "profiles" / "dev" / "config.toml"
    production_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    production_path.write_text('[demo]\ntoken = "prod"\n', encoding="utf-8")
    profile_path.write_text('[demo]\ntoken = "dev"\n', encoding="utf-8")
    monkeypatch.setenv("AXM_PROFILE", "dev")

    assert axm_config.get_file("demo", "token", default="sentinel") == "dev"
