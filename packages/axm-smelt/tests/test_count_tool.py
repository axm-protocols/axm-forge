from __future__ import annotations

import importlib.metadata

import pytest

from axm_smelt.tools.count import SmeltCountTool


@pytest.fixture
def tool() -> SmeltCountTool:
    return SmeltCountTool()


# ── Unit tests ────────────────────────────────────────────────────────


def test_count_tool_name(tool: SmeltCountTool) -> None:
    assert tool.name == "smelt_count"


def test_count_tool_basic(tool: SmeltCountTool) -> None:
    result = tool.execute(data="hello world")
    assert result.success is True
    assert result.data is not None
    assert result.data["tokens"] > 0


def test_count_tool_model(tool: SmeltCountTool) -> None:
    result = tool.execute(data="test", model="o200k_base")
    assert result.success is True
    assert result.data["model"] == "o200k_base"


def test_count_tool_error(tool: SmeltCountTool) -> None:
    result = tool.execute(data=None)
    assert result.success is False


def test_count_tool_agent_hint() -> None:
    assert isinstance(SmeltCountTool.agent_hint, str)
    assert len(SmeltCountTool.agent_hint) > 0


# ── Functional tests ──────────────────────────────────────────────────


def test_entry_point_smelt_count() -> None:
    eps = importlib.metadata.entry_points(group="axm.tools")
    matched = [e for e in eps if e.name == "smelt_count"]
    assert len(matched) == 1


# ── Edge cases ────────────────────────────────────────────────────────


def test_count_empty_data(tool: SmeltCountTool) -> None:
    result = tool.execute(data="")
    assert result.success is True
    assert isinstance(result.data["tokens"], int)
