from __future__ import annotations

import importlib.metadata
import json

import pytest

from axm_smelt.tools.smelt import SmeltTool


@pytest.fixture
def tool() -> SmeltTool:
    return SmeltTool()


@pytest.fixture
def sample_json() -> str:
    return json.dumps({"a": 1, "b": 2, "c": [1, 2, 3], "d": {"nested": True}})


# ── Unit tests ────────────────────────────────────────────────────────


def test_tool_name(tool: SmeltTool) -> None:
    assert tool.name == "smelt"


def test_tool_execute_json(tool: SmeltTool) -> None:
    result = tool.execute(data='{"a": 1, "b": 2}')
    assert result.success is True
    assert result.data is not None
    # result.data should contain compacted output
    assert "compacted" in result.data or "original_tokens" in str(result.data)


def test_smelt_tool_format(tool: SmeltTool) -> None:
    result = tool.execute(data='{"a":1}')
    assert result.success is True
    assert result.data["format"] == "json"


def test_smelt_tool_agent_hint() -> None:
    assert isinstance(SmeltTool.agent_hint, str)
    assert len(SmeltTool.agent_hint) > 0


def test_tool_execute_with_preset(tool: SmeltTool, sample_json: str) -> None:
    result = tool.execute(data=sample_json, preset="safe")
    assert result.success is True
    assert result.data is not None


def test_tool_execute_with_strategies(tool: SmeltTool, sample_json: str) -> None:
    result = tool.execute(data=sample_json, strategies=["minify"])
    assert result.success is True
    assert result.data is not None


def test_tool_execute_error(tool: SmeltTool) -> None:
    result = tool.execute(data=None)
    assert result.success is False
    assert result.error is not None
    assert len(result.error) > 0


def test_tool_execute_empty(tool: SmeltTool) -> None:
    result = tool.execute(data="")
    assert result.success is True


# ── Functional tests ──────────────────────────────────────────────────


def test_tool_roundtrip(tool: SmeltTool, sample_json: str) -> None:
    result = tool.execute(data=sample_json, preset="safe")
    assert result.success is True
    # Parse compacted output — should be lossless with safe preset
    data = result.data
    # Extract compacted text from result data
    if isinstance(data, dict):
        compacted = data.get("compacted", "")
    else:
        compacted = str(data)
    parsed_output = json.loads(compacted)
    parsed_input = json.loads(sample_json)
    assert parsed_output == parsed_input


def test_entry_point_resolution() -> None:
    eps = importlib.metadata.entry_points(group="axm.tools")
    matched = [e for e in eps if e.name == "smelt"]
    assert len(matched) == 1
    tool_cls = matched[0].load()
    assert tool_cls.__name__ == "SmeltTool"


# ── Edge cases ────────────────────────────────────────────────────────


def test_large_input(tool: SmeltTool) -> None:
    # ~1MB JSON string
    large = json.dumps({"items": [{"id": i, "value": "x" * 100} for i in range(5000)]})
    assert len(large) > 500_000
    result = tool.execute(data=large)
    assert result.success is True
    assert result.data is not None


def test_non_string_data(tool: SmeltTool) -> None:
    result = tool.execute(data=42)
    # Should convert to string or return error gracefully
    assert isinstance(result.success, bool)
    if result.success:
        assert result.data is not None
    else:
        assert result.error is not None


def test_invalid_preset(tool: SmeltTool) -> None:
    result = tool.execute(data='{"a": 1}', preset="bad")
    assert result.success is False
    assert result.error is not None
    assert len(result.error) > 0
