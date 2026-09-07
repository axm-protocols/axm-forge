"""Tests for serve-mode settings resolution."""

from __future__ import annotations

import importlib
from pathlib import Path

import axm_config
import pytest


def test_env_tier_selects_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: the environment tier selects shared without an explicit value."""
    monkeypatch.setenv("AXM_MCP_SERVE_MODE", "shared")
    settings = importlib.import_module("axm_mcp.settings")

    assert settings.resolve_serve_mode(None) == "shared"


def test_explicit_mode_outranks_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: an explicit shared value outranks a dedicated environment value."""
    monkeypatch.setenv("AXM_MCP_SERVE_MODE", "dedicated")
    settings = importlib.import_module("axm_mcp.settings")

    assert settings.resolve_serve_mode("shared") == "shared"


def test_invalid_resolved_mode_names_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: an invalid resolved mode raises ValueError naming that value."""
    monkeypatch.setenv("AXM_MCP_SERVE_MODE", "bogus")
    settings = importlib.import_module("axm_mcp.settings")

    with pytest.raises(ValueError, match="bogus"):
        settings.resolve_serve_mode(None)


def test_production_profile_keeps_historic_pid_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: production keeps the exact PID path used by write_pid today."""
    monkeypatch.delenv("AXM_PROFILE", raising=False)
    settings = importlib.import_module("axm_mcp.settings")

    expected = Path.home() / ".axm" / "mcp-server.pid"
    assert str(settings.resolve_pid_file()) == str(expected)


def test_production_profile_keeps_http_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: production without an override keeps HTTP port 9427."""
    monkeypatch.delenv("AXM_PROFILE", raising=False)
    monkeypatch.delenv("AXM_MCP_PORT", raising=False)
    settings = importlib.import_module("axm_mcp.settings")

    assert settings.resolve_http_port() == 9427


def test_dev_profile_uses_distinct_profile_pid_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: dev uses its axm-config profile directory and a distinct PID path."""
    settings = importlib.import_module("axm_mcp.settings")
    monkeypatch.setenv("AXM_PROFILE", "dev")
    dev_root = axm_config.profile_root()
    dev_pid = settings.resolve_pid_file()
    monkeypatch.delenv("AXM_PROFILE", raising=False)
    production_pid = settings.resolve_pid_file()

    assert dev_root is not None
    assert dev_pid.is_relative_to(dev_root)
    assert dev_pid != production_pid


def test_dev_profile_without_port_override_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: dev without AXM_MCP_PORT raises the typed refusal error."""
    monkeypatch.setenv("AXM_PROFILE", "dev")
    monkeypatch.delenv("AXM_MCP_PORT", raising=False)
    settings = importlib.import_module("axm_mcp.settings")
    error_type = settings.NonProductionPortError

    with pytest.raises(error_type) as exc_info:
        settings.resolve_http_port()

    assert "AXM_MCP_PORT" in str(exc_info.value)
