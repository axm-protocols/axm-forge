from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from axm_ast.tools.context import ContextTool


@pytest.fixture
def workspace_ctx():
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
def tool():
    return ContextTool()


class TestWorkspaceContextSlim:
    def test_workspace_context_slim(self, tool, workspace_ctx, tmp_path, monkeypatch):
        """slim=True on workspace returns compact format.

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

        result = tool.execute(path=str(tmp_path), slim=True)

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

    def test_workspace_context_depth0(self, tool, workspace_ctx, tmp_path, monkeypatch):
        """depth=0 on workspace returns same compact format as slim."""
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace",
            lambda p: MagicMock(),
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_context",
            lambda p: workspace_ctx,
        )

        result = tool.execute(path=str(tmp_path), depth=0)

        assert result.success is True
        data = result.data
        for pkg in data["packages"]:
            assert list(pkg.keys()) == ["name"]
        assert "package_graph" not in data

    def test_workspace_context_depth1(self, tool, workspace_ctx, tmp_path, monkeypatch):
        """depth=1 on workspace returns full output with stats and graph."""
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace",
            lambda p: MagicMock(),
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_context",
            lambda p: workspace_ctx,
        )

        result = tool.execute(path=str(tmp_path), depth=1)

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
    def test_non_workspace_slim(self, tool, tmp_path, monkeypatch):
        """Regular package + slim=True uses format_context_json with depth=0."""
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

        result = tool.execute(path=str(tmp_path), slim=True)

        assert result.success is True
        assert result.data == expected_data

    def test_workspace_high_depth(self, tool, workspace_ctx, tmp_path, monkeypatch):
        """depth=3 on workspace returns full workspace context (same as depth=1)."""
        monkeypatch.setattr(
            "axm_ast.core.workspace.detect_workspace",
            lambda p: MagicMock(),
        )
        monkeypatch.setattr(
            "axm_ast.core.workspace.build_workspace_context",
            lambda p: workspace_ctx,
        )

        result = tool.execute(path=str(tmp_path), depth=3)

        assert result.success is True
        data = result.data
        # Full output same as depth>=1
        for pkg in data["packages"]:
            assert "module_count" in pkg
            assert "function_count" in pkg
        assert "package_graph" in data
