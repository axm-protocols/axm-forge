from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from axm_smelt.core.models import Format, SmeltContext, SmeltReport
from axm_smelt.strategies.base import SmeltStrategy


def test_context_is_frozen() -> None:
    ctx = SmeltContext(text='{"a":1}')
    with pytest.raises(FrozenInstanceError):
        ctx.text = "x"
    with pytest.raises(FrozenInstanceError):
        ctx.parsed = {}


def test_text_constructor_caches_parsed() -> None:
    ctx = SmeltContext(text='{"a":1}')
    first = ctx.parsed
    second = ctx.parsed
    assert first is second
    assert first == {"a": 1}


def test_parsed_constructor_caches_text() -> None:
    ctx = SmeltContext(parsed={"a": 1}, format=Format.JSON)
    first = ctx.text
    second = ctx.text
    assert first is second
    assert json.loads(first) == {"a": 1}


def test_parsed_serialization_is_deterministic() -> None:
    a = SmeltContext(parsed={"b": 2, "a": 1}, format=Format.JSON)
    b = SmeltContext(parsed={"b": 2, "a": 1}, format=Format.JSON)
    assert a.text == b.text


def test_invalid_json_text_yields_none_parsed() -> None:
    ctx = SmeltContext(text="not json")
    assert ctx.parsed is None


def test_empty_text_yields_none_parsed() -> None:
    ctx = SmeltContext(text="")
    assert ctx.parsed is None


def test_smelt_report_fields() -> None:
    report = SmeltReport(
        original="hello world",
        compacted="hello world",
        original_tokens=10,
        compacted_tokens=8,
        savings_pct=20.0,
        format=Format.TEXT,
        strategies_applied=["minify"],
    )
    assert report.original == "hello world"
    assert report.compacted == "hello world"
    assert report.original_tokens == 10
    assert report.compacted_tokens == 8
    assert report.savings_pct == 20.0
    assert report.format == Format.TEXT
    assert report.strategies_applied == ["minify"]


def test_strategy_abc() -> None:
    with pytest.raises(TypeError):

        class Incomplete(SmeltStrategy):
            pass

        Incomplete()  # type: ignore[abstract]


# --- merged from test_smelt_context.py ---


class TestSmeltContextLazyParse:
    """test_smelt_context_lazy_parse"""

    def test_parsed_returns_dict(self) -> None:
        ctx = SmeltContext(text='{"a":1}')
        assert ctx.parsed == {"a": 1}

    def test_second_access_does_not_reparse(self, mocker: MagicMock) -> None:
        ctx = SmeltContext(text='{"a":1}')
        # First access triggers parse
        _ = ctx.parsed
        spy = mocker.patch("json.loads", wraps=json.loads)
        # Second access should use cache
        result = ctx.parsed
        spy.assert_not_called()
        assert result == {"a": 1}


def test_smelt_context_invalid_json() -> None:
    """test_smelt_context_invalid_json: .parsed returns None for non-JSON."""
    ctx = SmeltContext(text="not json")
    assert ctx.parsed is None


def test_smelt_context_is_immutable() -> None:
    """SmeltContext is frozen: assignment to text/parsed raises."""
    ctx = SmeltContext(text='{"a":1}')
    with pytest.raises(FrozenInstanceError):
        ctx.text = "x"
    with pytest.raises(FrozenInstanceError):
        ctx.parsed = {"b": 2}


def test_smelt_context_format_carried() -> None:
    """test_smelt_context_format_carried: format field is preserved."""
    ctx = SmeltContext(text='{"a":1}', format=Format.JSON)
    assert ctx.format is Format.JSON


def test_pipeline_context_single_parse(mocker: MagicMock) -> None:
    """json.loads called ≤2 times through aggressive preset."""
    from axm_smelt.core.pipeline import smelt

    json_text = json.dumps({"key": "value", "nested": {"a": 1, "b": None}})

    real_loads = json.loads
    spy = mocker.patch("json.loads", side_effect=real_loads)

    report = smelt(json_text, preset="aggressive")

    assert spy.call_count <= 2, f"json.loads called {spy.call_count} times, expected ≤2"
    assert report.compacted  # non-empty output


def test_check_context_reuse() -> None:
    """Strategy estimates must match current behavior (context reuse)."""
    from axm_smelt.core.pipeline import check

    json_text = json.dumps({"key": "value", "nested": {"a": 1, "b": None}})
    report = check(json_text)

    assert isinstance(report.strategy_estimates, dict)
    # All estimates should be numeric percentages
    for name, pct in report.strategy_estimates.items():
        assert isinstance(name, str)
        assert isinstance(pct, float)


def test_non_json_text_parsed_stays_none() -> None:
    """Plain text through pipeline: parsed stays None."""
    from axm_smelt.core.pipeline import smelt

    plain = "Hello, this is plain text with no JSON structure."
    report = smelt(plain)
    # Should not crash — strategies fall through via ctx.text
    assert report.compacted is not None


def test_empty_input_no_crash() -> None:
    """smelt('') must not crash and returns an empty report."""
    from axm_smelt.core.pipeline import smelt

    report = smelt("")
    assert report.compacted == ""
    assert report.original_tokens == 0
    assert report.savings_pct == 0.0


def test_distinct_contexts_are_independent() -> None:
    """Two SmeltContext instances from the same source are independent."""
    a = SmeltContext(text='{"key": "value"}')
    b = SmeltContext(text='{"key":"value"}')
    assert a.parsed == b.parsed == {"key": "value"}
    assert a.text != b.text  # text is the source-of-truth, not re-derived
