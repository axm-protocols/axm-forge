"""Unit tests for DocsTool — pure, no I/O (plus dogfood smoke test)."""

from __future__ import annotations

from pathlib import Path

from axm_ast.tools.docs import DocsTool

SELF_ROOT = Path(__file__).resolve().parents[3]


class TestDocsToolUnit:
    """Tests for ast_docs tool."""

    def test_has_name(self) -> None:
        tool = DocsTool()
        assert tool.name == "ast_docs"

    def test_docs_bad_path(self) -> None:
        tool = DocsTool()
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False


# ─── Dogfood: docs tool on self ────────────────────────────────────────────


def test_docs_on_self() -> None:
    tool = DocsTool()
    result = tool.execute(path=str(SELF_ROOT))
    assert result.success is True
    assert result.data["readme"] is not None
