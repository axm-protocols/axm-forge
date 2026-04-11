from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from axm_ast.tools.context import ContextTool


@pytest.fixture()
def _no_workspace(tmp_path):
    """Patch detect_workspace to return None (single-package mode)."""
    with patch("axm_ast.core.workspace.detect_workspace", return_value=None) as mock:
        yield mock


@pytest.fixture()
def _mock_context(tmp_path):
    """Patch build_context and format_context_json."""
    sentinel_ctx = MagicMock(name="built_context")

    def _format(ctx, *, depth=1):
        if depth is None:
            return {
                "modules": ["mod_a", "mod_b"],
                "dependency_graph": {"mod_a": ["mod_b"]},
            }
        if depth == 0:
            return {"top_modules": ["mod_a"]}
        if depth == 1:
            return {"packages": ["pkg_a"]}
        return {"symbols": ["sym_a"]}

    with (
        patch("axm_ast.core.context.build_context", return_value=sentinel_ctx),
        patch("axm_ast.core.context.format_context_json", side_effect=_format),
    ):
        yield


# ── Unit tests ──────────────────────────────────────────────────────


@pytest.mark.usefixtures("_no_workspace", "_mock_context")
def test_context_tool_depth_none(tmp_path):
    """depth=None triggers full context with modules and dependency_graph."""
    result = ContextTool().execute(path=str(tmp_path), depth=None)
    assert result.success
    assert "modules" in result.data
    assert "dependency_graph" in result.data


@pytest.mark.usefixtures("_no_workspace", "_mock_context")
def test_context_tool_default_depth(tmp_path):
    """Omitting depth defaults to 1 — returns packages, not modules."""
    result = ContextTool().execute(path=str(tmp_path))
    assert result.success
    assert "packages" in result.data
    assert "modules" not in result.data


@pytest.mark.usefixtures("_no_workspace", "_mock_context")
def test_context_tool_depth0_overrides_none(tmp_path):
    """depth=0 explicitly produces compact output (top_modules)."""
    result = ContextTool().execute(path=str(tmp_path), depth=0)
    assert result.success
    assert "top_modules" in result.data


# ── Edge cases ──────────────────────────────────────────────────────


@pytest.mark.usefixtures("_no_workspace", "_mock_context")
def test_context_tool_mcp_null_depth(tmp_path):
    """MCP JSON null is parsed as Python None — must trigger full context."""
    # Simulate what MCP transport does: JSON `{"depth": null}` → Python None
    depth_from_json: int | None = None
    result = ContextTool().execute(path=str(tmp_path), depth=depth_from_json)
    assert result.success
    assert "modules" in result.data
    assert "dependency_graph" in result.data


@pytest.mark.usefixtures("_no_workspace", "_mock_context")
def test_context_tool_explicit_depth_1_matches_default(tmp_path):
    """Explicit depth=1 produces the same output as omitting depth."""
    default_result = ContextTool().execute(path=str(tmp_path))
    explicit_result = ContextTool().execute(path=str(tmp_path), depth=1)
    assert default_result.data == explicit_result.data
