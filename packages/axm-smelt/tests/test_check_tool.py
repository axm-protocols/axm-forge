from __future__ import annotations

import importlib.metadata
import json

import pytest

from axm_smelt.tools.check import SmeltCheckTool


@pytest.fixture
def tool() -> SmeltCheckTool:
    return SmeltCheckTool()


@pytest.fixture
def json_text() -> str:
    return json.dumps({"a": 1, "b": None})


# ── Unit tests ────────────────────────────────────────────────────────


def test_check_tool_name(tool: SmeltCheckTool) -> None:
    assert tool.name == "smelt_check"


def test_check_tool_json(tool: SmeltCheckTool, json_text: str) -> None:
    result = tool.execute(data=json_text)
    assert result.success is True
    assert result.data is not None
    assert "format" in result.data
    assert "tokens" in result.data
    assert "strategy_estimates" in result.data


def test_check_tool_estimates(tool: SmeltCheckTool, json_text: str) -> None:
    result = tool.execute(data=json_text)
    assert result.success is True
    estimates = result.data["strategy_estimates"]
    assert estimates["drop_nulls"] > 0


def test_check_tool_error(tool: SmeltCheckTool) -> None:
    result = tool.execute(data=None)
    assert result.success is False


def test_check_tool_agent_hint() -> None:
    assert isinstance(SmeltCheckTool.agent_hint, str)
    assert len(SmeltCheckTool.agent_hint) > 0


# ── Functional tests ──────────────────────────────────────────────────


def test_check_tool_roundtrip_with_cli(tool: SmeltCheckTool, json_text: str) -> None:
    from axm_smelt.core.pipeline import check

    tool_result = tool.execute(data=json_text)
    cli_report = check(json_text)

    assert tool_result.data["format"] == cli_report.format.value
    assert tool_result.data["tokens"] == cli_report.original_tokens
    assert tool_result.data["strategy_estimates"] == cli_report.strategy_estimates


def test_entry_point_smelt_check() -> None:
    eps = importlib.metadata.entry_points(group="axm.tools")
    matched = [e for e in eps if e.name == "smelt_check"]
    assert len(matched) == 1


# ── Edge cases ────────────────────────────────────────────────────────


def test_check_non_string_data(tool: SmeltCheckTool) -> None:
    result = tool.execute(data={"a": 1})
    assert result.success is True
    assert result.data["format"] == "json"
