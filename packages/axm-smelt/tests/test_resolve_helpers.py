from __future__ import annotations

import json

import pytest

from axm_smelt.core.pipeline import _resolve_input, _resolve_strategies
from axm_smelt.strategies import get_preset

# ── Unit tests: _resolve_input ──────────────────────────────────────


def test_resolve_input_text_only() -> None:
    text, parsed = _resolve_input(text="hello", parsed=None)
    assert text == "hello"
    assert parsed is None


def test_resolve_input_parsed_dict() -> None:
    data = {"a": 1}
    text, parsed = _resolve_input(text=None, parsed=data)
    assert text == json.dumps(data, separators=(",", ":"))
    assert parsed is data


def test_resolve_input_neither() -> None:
    with pytest.raises(ValueError, match="Either text or parsed must be provided"):
        _resolve_input(text=None, parsed=None)


def test_resolve_input_parsed_overrides_text() -> None:
    """When both text and parsed are provided, parsed takes precedence."""
    data = {"key": "value"}
    text, parsed = _resolve_input(text="ignored", parsed=data)
    assert text == json.dumps(data, separators=(",", ":"))
    assert parsed is data


def test_resolve_input_parsed_list() -> None:
    data = [1, 2, 3]
    text, parsed = _resolve_input(text=None, parsed=data)
    assert text == json.dumps(data, separators=(",", ":"))
    assert parsed is data


# ── Unit tests: _resolve_strategies ─────────────────────────────────


def test_resolve_strategies_explicit() -> None:
    strats = _resolve_strategies(["minify"], None)
    assert len(strats) == 1
    assert strats[0].name == "minify"


def test_resolve_strategies_preset() -> None:
    strats = _resolve_strategies(None, "safe")
    expected = get_preset("safe")
    assert [s.name for s in strats] == [s.name for s in expected]


def test_resolve_strategies_default() -> None:
    """No strategies and no preset falls back to safe preset."""
    strats = _resolve_strategies(None, None)
    expected = get_preset("safe")
    assert [s.name for s in strats] == [s.name for s in expected]


# ── Edge cases ──────────────────────────────────────────────────────


def test_smelt_zero_token_input() -> None:
    from axm_smelt.core.pipeline import smelt

    report = smelt(text="")
    assert report.savings_pct == 0.0
    assert report.original == ""
    assert report.compacted_tokens >= 0


def test_smelt_all_strategies_regress() -> None:
    """When every strategy increases tokens, original text is returned."""
    from axm_smelt.core.pipeline import smelt

    # Plain short text unlikely to be compacted further
    text = "a"
    report = smelt(text=text, strategies=["minify"])
    # Original text preserved (or identical output)
    assert report.compacted == text or report.strategies_applied == []
