"""Unit tests for ContextTool — pure, no I/O."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_ast.tools.context import ContextTool

# ─── ContextTool ────────────────────────────────────────────────────────────


REPO = Path(__file__).resolve().parents[3]
SELF_PKG = Path(__file__).resolve().parents[3] / "src" / "axm_ast"


def test_tool_returns_text_and_data() -> None:
    """ContextTool returns both structured data and text rendering."""
    tool = ContextTool()
    result = tool.execute(path=str(REPO), depth=1)
    assert result.success
    assert "name" in result.data
    assert "packages" in result.data
    assert result.text is not None
    assert "axm" in result.text.lower()


def test_text_token_count_lower() -> None:
    """Text rendering is more compact than JSON."""
    tool = ContextTool()
    result = tool.execute(path=str(REPO), depth=1)
    assert result.success
    json_str = json.dumps(result.data)
    assert result.text is not None
    text_tokens = len(result.text.split())
    json_tokens = len(json_str.split())
    assert text_tokens < json_tokens


def test_workspace() -> None:
    """ContextTool works on workspace root."""
    ws_path = Path(__file__).resolve().parent.parent.parent.parent.parent
    tool = ContextTool()
    result = tool.execute(path=str(ws_path), depth=1)
    if not result.success:
        pytest.skip("workspace detection not available in test environment")
    assert result.text is not None
    assert "axm" in result.text.lower()


def test_slim_param_ignored() -> None:
    """Calling ContextTool with slim=True produces same output as without."""
    tool = ContextTool()
    normal = tool.execute(path=str(REPO), depth=1)
    with_slim = tool.execute(path=str(REPO), depth=1, slim=True)
    assert normal.data == with_slim.data


# ─── TestContextToolUnit (from test_tools.py) ──────────────────────────────


class TestContextToolUnit:
    """Tests for ast_context tool."""

    def test_has_name(self) -> None:
        tool = ContextTool()
        assert tool.name == "ast_context"

    def test_is_axm_tool(self) -> None:
        tool = ContextTool()
        assert hasattr(tool, "execute")
        assert hasattr(tool, "name")

    def test_execute_bad_path(self) -> None:
        tool = ContextTool()
        result = tool.execute(path="/nonexistent/path")
        assert result.success is False
        assert result.error is not None


# ─── Dogfood: context tool on self ─────────────────────────────────────────


def test_context_on_self() -> None:
    tool = ContextTool()
    result = tool.execute(path=str(SELF_PKG))
    assert result.success is True
    assert result.data["name"] == "axm_ast"


# ─── Workspace context depth tests (from test_workspace_context_depth.py) ──


@pytest.fixture
def workspace_ctx() -> dict[str, Any]:
    """Full workspace context as returned by build_workspace_context."""
    return {
        "workspace": "test-ws",
        "root": "/tmp/test-ws",
        "package_count": 2,
        "packages": [
            {
                "name": "pkg-a",
                "root": "/tmp/test-ws/packages/pkg-a",
                "module_count": 3,
                "function_count": 10,
                "class_count": 2,
            },
            {
                "name": "pkg-b",
                "root": "/tmp/test-ws/packages/pkg-b",
                "module_count": 5,
                "function_count": 20,
                "class_count": 4,
            },
        ],
        "package_graph": {"pkg-a": ["pkg-b"], "pkg-b": []},
    }


@pytest.fixture
def context_tool() -> ContextTool:
    return ContextTool()


class TestWorkspaceContextDepth0:
    def test_workspace_context_depth0(
        self,
        context_tool: ContextTool,
        workspace_ctx: dict[str, Any],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """depth=0 on workspace returns compact format.

        Name-only packages, no graph.
        """
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace",
            lambda p: MagicMock(),
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_context",
            lambda p: workspace_ctx,
        )

        result = context_tool.execute(path=str(tmp_path), depth=0)

        assert result.success is True
        data = result.data
        # Compact: packages should be name-only dicts
        for pkg in data["packages"]:
            assert list(pkg.keys()) == ["name"]
        # No package_graph in compact mode
        assert "package_graph" not in data
        # Workspace name and count still present
        assert data["workspace"] == "test-ws"
        assert data["package_count"] == 2

    def test_workspace_context_depth0_compact_like_slim(
        self,
        context_tool: ContextTool,
        workspace_ctx: dict[str, Any],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """depth=0 on workspace returns same compact format as slim."""
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace",
            lambda p: MagicMock(),
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_context",
            lambda p: workspace_ctx,
        )

        result = context_tool.execute(path=str(tmp_path), depth=0)

        assert result.success is True
        data = result.data
        for pkg in data["packages"]:
            assert list(pkg.keys()) == ["name"]
        assert "package_graph" not in data

    def test_workspace_context_depth1(
        self,
        context_tool: ContextTool,
        workspace_ctx: dict[str, Any],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """depth=1 on workspace returns full output with stats and graph."""
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace",
            lambda p: MagicMock(),
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_context",
            lambda p: workspace_ctx,
        )

        result = context_tool.execute(path=str(tmp_path), depth=1)

        assert result.success is True
        data = result.data
        # Full: packages have stats
        for pkg in data["packages"]:
            assert "module_count" in pkg
            assert "function_count" in pkg
            assert "class_count" in pkg
        # Graph present
        assert "package_graph" in data


class TestWorkspaceContextEdgeCases:
    def test_non_workspace_depth0(
        self,
        context_tool: ContextTool,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regular package + depth=0 uses format_context_json with depth=0."""
        mock_ctx = MagicMock()
        expected_data = {"name": "pkg", "top_symbols": []}

        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace",
            lambda p: None,
        )
        monkeypatch.setattr(
            "axm_ast.core.context.build_context",
            lambda p: mock_ctx,
        )
        monkeypatch.setattr(
            "axm_ast.core.context.format_context_json",
            lambda ctx, depth: expected_data if depth == 0 else {"full": ["all"]},
        )

        result = context_tool.execute(path=str(tmp_path), depth=0)

        assert result.success is True
        assert result.data == expected_data

    def test_workspace_high_depth(
        self,
        context_tool: ContextTool,
        workspace_ctx: dict[str, Any],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """depth=3 on workspace returns full workspace context (same as depth=1)."""
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace",
            lambda p: MagicMock(),
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_context",
            lambda p: workspace_ctx,
        )

        result = context_tool.execute(path=str(tmp_path), depth=3)

        assert result.success is True
        data = result.data
        # Full output same as depth>=1
        for pkg in data["packages"]:
            assert "module_count" in pkg
            assert "function_count" in pkg
        assert "package_graph" in data
