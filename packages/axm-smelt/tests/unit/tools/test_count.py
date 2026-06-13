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


def test_count_tool_text_carries_all_fields(tool: SmeltCountTool) -> None:
    result = tool.execute(data="hello world")
    assert result.text is not None
    assert result.text.startswith("smelt_count |")
    # no information lost: tokens, chars and model all rendered
    assert f"{result.data['tokens']} tokens" in result.text
    assert "11 chars" in result.text
    assert result.data["model"] in result.text


def test_entry_point_smelt_count() -> None:
    eps = importlib.metadata.entry_points(group="axm.tools")
    matched = [e for e in eps if e.name == "smelt_count"]
    assert len(matched) == 1


# ── Edge cases ────────────────────────────────────────────────────────


def test_count_empty_data(tool: SmeltCountTool) -> None:
    result = tool.execute(data="")
    assert result.success is True
    assert isinstance(result.data["tokens"], int)


def test_count_exposes_counter_backend(tool: SmeltCountTool) -> None:
    """AC1: data and text expose the actual tiktoken backend used."""
    result = tool.execute(data="hello world", model="o200k_base")
    assert result.success is True
    assert result.data["counter_backend"] == "tiktoken"
    assert "tiktoken" in result.text


def test_count_reports_fallback_backend(tool: SmeltCountTool) -> None:
    """AC3: an unknown model triggers fallback, reported as such (not as exact)."""
    result = tool.execute(data="hello world", model="definitely-not-a-real-model-xyz")
    assert result.success is True
    assert result.data["counter_backend"] == "fallback"
    assert "fallback" in result.text
