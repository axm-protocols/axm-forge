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
