"""Integration tests for live AXM configuration resolution."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.mark.integration
def test_config_file_selects_shared(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: a real AXM config file selects shared when the env tier is absent."""
    monkeypatch.delenv("AXM_MCP_SERVE_MODE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    config_path = tmp_path / ".axm" / "config.toml"
    config_path.parent.mkdir()
    config_path.write_text('[mcp]\nserve_mode = "shared"\n')
    settings = importlib.import_module("axm_mcp.settings")

    assert settings.resolve_serve_mode(None) == "shared"


@pytest.mark.integration
def test_config_edit_is_visible_on_next_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: rewriting one config file changes the next unchanged resolution."""
    monkeypatch.delenv("AXM_MCP_SERVE_MODE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    config_path = tmp_path / ".axm" / "config.toml"
    config_path.parent.mkdir()
    config_path.write_text('[mcp]\nserve_mode = "shared"\n')
    settings = importlib.import_module("axm_mcp.settings")

    first = settings.resolve_serve_mode(None)
    config_path.write_text('[mcp]\nserve_mode = "dedicated"\n')
    second = settings.resolve_serve_mode(None)

    assert (first, second) == ("shared", "dedicated")
