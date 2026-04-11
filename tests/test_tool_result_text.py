from __future__ import annotations

import dataclasses

import pytest

from axm.tools.base import ToolResult

# --- Unit tests ---


def test_tool_result_text_field_default():
    r = ToolResult(success=True)
    assert r.text is None


def test_tool_result_text_field_set():
    r = ToolResult(success=True, text="# Hi")
    assert r.text == "# Hi"


def test_tool_result_text_with_data():
    r = ToolResult(success=True, data={"k": 1}, text="k: 1")
    assert r.data == {"k": 1}
    assert r.text == "k: 1"


def test_tool_result_frozen_text():
    r = ToolResult(success=True, text="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.text = "y"  # type: ignore[misc]


def test_tool_result_backward_compat():
    r = ToolResult(success=True, data={}, error=None, hint=None)
    assert r.text is None


# --- Edge cases ---


def test_tool_result_text_empty_string():
    r = ToolResult(success=True, text="")
    assert r.text == ""
    assert r.text is not None


def test_tool_result_text_multiline_markdown():
    md = "| a | b |\n|---|---|\n| 1 | 2 |"
    r = ToolResult(success=True, text=md)
    assert r.text == md
