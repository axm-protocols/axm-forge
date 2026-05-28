"""Tests for AXM_DISABLE_TOOLS env var filtering in discovery."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from axm_mcp.discovery import _is_disabled, discover_tools

# ────────────────────────── _is_disabled unit tests ──────────────────────────


class TestIsDisabled:
    """Unit tests for the _is_disabled helper."""

    def test_exact_match(self) -> None:
        assert _is_disabled("ast_dead_code", ["ast_dead_code"]) is True

    def test_glob_match(self) -> None:
        assert _is_disabled("bib_search", ["bib_*"]) is True

    def test_no_match(self) -> None:
        assert _is_disabled("git_commit", ["bib_*"]) is False

    def test_empty_patterns(self) -> None:
        assert _is_disabled("anything", []) is False

    def test_multiple_patterns_first_matches(self) -> None:
        assert _is_disabled("bib_search", ["bib_*", "ast_*"]) is True

    def test_multiple_patterns_second_matches(self) -> None:
        assert _is_disabled("ast_inspect", ["bib_*", "ast_*"]) is True

    def test_multiple_patterns_none_matches(self) -> None:
        assert _is_disabled("git_commit", ["bib_*", "ast_dead_code"]) is False

    def test_wildcard_matches_all(self) -> None:
        assert _is_disabled("anything", ["*"]) is True


# ────────────────────────── discover_tools integration ───────────────────────


class _FakeEntryPoint:
    """Minimal entry point stub for testing discovery filtering."""

    def __init__(self, name: str) -> None:
        self.name = name

    def load(self) -> Any:
        """Return a plain callable (dispatcher pattern)."""

        def _dummy(**kwargs: Any) -> dict[str, Any]:
            return {"tool": self.name}

        _dummy.__doc__ = f"Fake tool {self.name}."
        return _dummy


_FAKE_EPS = [
    _FakeEntryPoint("ast_context"),
    _FakeEntryPoint("ast_dead_code"),
    _FakeEntryPoint("ast_diff"),
    _FakeEntryPoint("bib_search"),
    _FakeEntryPoint("bib_resolve"),
    _FakeEntryPoint("git_commit"),
]


def _mock_entry_points(group: str) -> list[_FakeEntryPoint]:
    """Return fake entry points for axm.tools group."""
    if group == "axm.tools":
        return list(_FAKE_EPS)
    return []


class TestDiscoverToolsFiltering:
    """Integration tests for discover_tools with AXM_DISABLE_TOOLS."""

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_no_env_var_discovers_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without AXM_DISABLE_TOOLS, all tools are discovered."""
        monkeypatch.delenv("AXM_DISABLE_TOOLS", raising=False)
        tools = discover_tools()
        assert len(tools) == 6
        assert "ast_context" in tools
        assert "bib_search" in tools

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_exact_name_excludes_tool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exact name excludes a single tool."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "ast_dead_code")
        tools = discover_tools()
        assert "ast_dead_code" not in tools
        assert "ast_context" in tools
        assert len(tools) == 5

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_glob_pattern_excludes_group(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Glob pattern excludes an entire tool group."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "bib_*")
        tools = discover_tools()
        assert "bib_search" not in tools
        assert "bib_resolve" not in tools
        assert "ast_context" in tools
        assert len(tools) == 4

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_multiple_patterns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple patterns (glob + exact) combine correctly."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "bib_*,ast_dead_code")
        tools = discover_tools()
        assert "bib_search" not in tools
        assert "bib_resolve" not in tools
        assert "ast_dead_code" not in tools
        assert "ast_context" in tools
        assert "git_commit" in tools
        assert len(tools) == 3

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_empty_string_discovers_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string means no filtering."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "")
        tools = discover_tools()
        assert len(tools) == 6

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_whitespace_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Whitespace around patterns is stripped."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", " bib_* , ast_dead_code ")
        tools = discover_tools()
        assert "bib_search" not in tools
        assert "ast_dead_code" not in tools
        assert len(tools) == 3

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_wildcard_disables_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Wildcard '*' disables all tools."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "*")
        tools = discover_tools()
        assert len(tools) == 0

    @patch("axm_mcp.discovery.importlib.metadata.entry_points", _mock_entry_points)
    def test_consecutive_commas_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Consecutive commas produce empty strings that are ignored."""
        monkeypatch.setenv("AXM_DISABLE_TOOLS", "bib_*,,ast_dead_code")
        tools = discover_tools()
        assert "bib_search" not in tools
        assert "ast_dead_code" not in tools
        assert len(tools) == 3
