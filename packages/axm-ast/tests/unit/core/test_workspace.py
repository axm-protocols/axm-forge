"""Unit tests for axm_ast.core.workspace pure parsing helpers."""

from __future__ import annotations

from axm_ast.core.workspace import _parse_workspace_members


class TestParsingUnit:
    """Pure-string parsing helpers (no I/O)."""

    def test_parse_workspace_members(self) -> None:
        text = '[tool.uv.workspace]\nmembers = ["pkg-a", "pkg-b"]'
        assert _parse_workspace_members(text) == ["pkg-a", "pkg-b"]

    def test_parse_workspace_members_multiline(self) -> None:
        text = '[tool.uv.workspace]\nmembers = [\n  "alpha",\n  "beta",\n]'
        assert _parse_workspace_members(text) == ["alpha", "beta"]

    def test_parse_workspace_members_no_section(self) -> None:
        text = '[project]\nname = "foo"'
        assert _parse_workspace_members(text) == []
