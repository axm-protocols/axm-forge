from __future__ import annotations

from pathlib import Path

import pytest

import axm_config


@pytest.mark.integration
def test_explicit_profile_returns_isolation_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC1: an explicit profile returns every state path and isolation verdict."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.delenv("AXM_PROFILE", raising=False)

    result = axm_config.ProfileIsolationTool().execute(profile="scratch")

    assert result.success is True
    assert {
        "tickets_db",
        "warden_socket",
        "warden_log",
        "sessions_root",
        "quality_dir",
        "protocols_dir",
        "isolated",
    } <= set(result.data)


@pytest.mark.integration
def test_implicit_profile_uses_axm_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC2: omitting profile resolves and reports the current AXM_PROFILE."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))
    monkeypatch.setenv("AXM_PROFILE", "lab")

    result = axm_config.ProfileIsolationTool().execute()

    assert result.success is True
    assert result.data["profile"] == "lab"


@pytest.mark.integration
def test_invalid_profile_returns_typed_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC3: an invalid profile is shaped as a failed ToolResult."""
    monkeypatch.setenv("AXM_HOME", str(tmp_path))

    result = axm_config.ProfileIsolationTool().execute(profile="../evil")

    assert result.success is False
    assert result.error
