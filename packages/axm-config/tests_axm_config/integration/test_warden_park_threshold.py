"""Integration coverage for the warden park-threshold configuration layers."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_config import paths


@pytest.mark.integration
def test_warden_park_threshold_reads_file_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: a [warden] file value under AXM_HOME is returned."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.delenv("AXM_WARDEN_PARK_THRESHOLD", raising=False)
    (tmp_path / "config.toml").write_text(
        "[warden]\npark_threshold = 7\n",
        encoding="utf-8",
    )

    assert paths.warden_park_threshold() == 7


@pytest.mark.integration
def test_warden_park_threshold_environment_outranks_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: the environment value wins over a [warden] file value."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    (tmp_path / "config.toml").write_text(
        "[warden]\npark_threshold = 7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AXM_WARDEN_PARK_THRESHOLD", "9")

    assert paths.warden_park_threshold() == 9
