"""Tests for DiffTool — structural diff between git refs."""

from __future__ import annotations

import pytest

from axm_ast.tools.diff import DiffTool


@pytest.fixture()
def tool() -> DiffTool:
    """Provide a fresh DiffTool instance."""
    return DiffTool()


# ─── Tool identity ──────────────────────────────────────────────────────────


class TestDiffToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: DiffTool) -> None:
        assert tool.name == "ast_diff"


# ─── Parameter validation ───────────────────────────────────────────────────


class TestDiffToolValidation:
    """Parameter validation tests."""

    def test_missing_base(self, tool: DiffTool) -> None:
        result = tool.execute(path=".", head="HEAD")
        assert result.success is False
        assert result.error is not None
        assert "base" in result.error

    def test_missing_head(self, tool: DiffTool) -> None:
        result = tool.execute(path=".", base="main")
        assert result.success is False
        assert result.error is not None
        assert "head" in result.error

    def test_bad_path(self, tool: DiffTool) -> None:
        result = tool.execute(path="/nonexistent/path", base="main", head="HEAD")
        assert result.success is False
