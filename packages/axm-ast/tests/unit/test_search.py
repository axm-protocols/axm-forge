"""Unit tests for SearchTool — pure identity and validation, no scan I/O."""

from __future__ import annotations

import pytest

from axm_ast.tools.search import SearchTool


@pytest.fixture()
def tool() -> SearchTool:
    """Provide a fresh SearchTool instance."""
    return SearchTool()


class TestSearchToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: SearchTool) -> None:
        assert tool.name == "ast_search"

    def test_has_agent_hint(self, tool: SearchTool) -> None:
        assert tool.agent_hint
