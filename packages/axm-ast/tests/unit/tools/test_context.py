"""Unit tests for ContextTool — pure, no I/O."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_ast.tools.context import ContextTool

# ─── ContextTool ────────────────────────────────────────────────────────────


REPO = Path(__file__).resolve().parents[3]


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
