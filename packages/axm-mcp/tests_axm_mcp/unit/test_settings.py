"""Tests for serve-mode settings resolution."""

from __future__ import annotations

import importlib

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
