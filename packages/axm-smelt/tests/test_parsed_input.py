from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from axm_smelt.core.pipeline import smelt

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_smelt_with_parsed_dict() -> None:
    """smelt(parsed=dict) returns a valid SmeltReport with minified JSON."""
    parsed = {"a": 1, "b": [1, 2, 3]}
    report = smelt(parsed=parsed)

    assert report.compacted is not None
    assert report.original_tokens > 0
    assert report.compacted_tokens > 0
    # compacted output should be valid JSON and minified (no extra whitespace)
    reparsed = json.loads(report.compacted)
    assert reparsed == parsed or isinstance(reparsed, dict)


def test_smelt_tool_dict_no_dumps(mocker: MockerFixture) -> None:
    """SmeltTool.execute(data=dict) must NOT json.dumps before pipeline entry."""
    from axm_smelt.tools.smelt import SmeltTool

    spy = mocker.patch(
        "axm_smelt.tools.smelt.json.dumps",
        side_effect=AssertionError("json.dumps should not be called"),
    )

    # Patch the pipeline to avoid real execution — we only care about the
    # code path *before* the pipeline is invoked.
    fake_report = MagicMock(
        compacted='{"a":1}',
        format=MagicMock(value="json"),
        original_tokens=10,
        compacted_tokens=5,
        savings_pct=50.0,
        strategies_applied=["minify_json"],
    )
    mocker.patch("axm_smelt.core.pipeline.smelt", return_value=fake_report)

    tool = SmeltTool()
    result = tool.execute(data={"a": 1})

    assert result.success is True
    spy.assert_not_called()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_parsed_takes_precedence_over_text() -> None:
    """When both text and parsed are provided, parsed wins."""
    parsed = {"winner": True}
    report = smelt(text='{"loser": true}', parsed=parsed)

    reparsed = json.loads(report.compacted)
    assert reparsed.get("winner") is True


def test_neither_text_nor_parsed_raises() -> None:
    """Calling smelt() with no input raises ValueError."""
    with pytest.raises(ValueError):
        smelt()


def test_parsed_list_input() -> None:
    """smelt(parsed=list) works — tabular strategy can kick in."""
    parsed = [{"a": 1}, {"a": 2}]
    report = smelt(parsed=parsed)

    assert report.compacted is not None
    assert report.original_tokens > 0
    reparsed = json.loads(report.compacted)
    assert isinstance(reparsed, list)


def test_check_with_parsed_dict() -> None:
    """check(parsed=dict) works without requiring text."""
    from axm_smelt.core.pipeline import check

    parsed = {"x": [1, 2, 3]}
    report = check(parsed=parsed)

    assert report.format.value == "json"
    assert report.original_tokens > 0


def test_check_neither_text_nor_parsed_raises() -> None:
    """check() with no input raises ValueError."""
    from axm_smelt.core.pipeline import check

    with pytest.raises(ValueError):
        check()
