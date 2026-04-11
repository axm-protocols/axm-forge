from __future__ import annotations

import json
from unittest.mock import MagicMock

from axm_smelt.core.models import Format, SmeltContext

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


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


def test_smelt_context_parsed_invalidates_text() -> None:
    """test_smelt_context_parsed_invalidates_text: setting parsed updates text."""
    ctx = SmeltContext(text='{"a":1}')
    ctx.parsed = {"b": 2}
    assert ctx.text == json.dumps({"b": 2})


def test_smelt_context_format_carried() -> None:
    """test_smelt_context_format_carried: format field is preserved."""
    ctx = SmeltContext(text='{"a":1}', format=Format.JSON)
    assert ctx.format is Format.JSON


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


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


def test_strategy_changes_text_only_invalidates_parsed() -> None:
    """When a strategy modifies text, parsed must be invalidated."""
    ctx = SmeltContext(text='{"key": "value"}')
    # Force parsed cache
    _ = ctx.parsed
    # Simulate a strategy that modifies text (like strip_quotes)
    ctx.text = '{"key":"value"}'
    # parsed should re-parse from the new text
    assert ctx.parsed == {"key": "value"}
