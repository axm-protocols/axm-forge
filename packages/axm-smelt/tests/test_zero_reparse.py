from __future__ import annotations

import json
from unittest.mock import patch

from axm_smelt import smelt
from axm_smelt.core.models import Format, SmeltContext
from axm_smelt.strategies.drop_nulls import DropNullsStrategy
from axm_smelt.strategies.flatten import FlattenStrategy
from axm_smelt.strategies.minify import MinifyStrategy
from axm_smelt.strategies.strip_quotes import StripQuotesStrategy
from axm_smelt.strategies.tabular import TabularStrategy

# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_minify_uses_ctx_format() -> None:
    """MinifyStrategy reads ctx.format instead of calling detect_format."""
    yaml_text = "a: 1\nb: 2\nc: 3\n"
    ctx = SmeltContext(text=yaml_text, format=Format.YAML)
    strategy = MinifyStrategy()

    with patch("axm_smelt.strategies.minify.detect_format") as mock_detect:
        result = strategy.apply(ctx)

    mock_detect.assert_not_called()
    # YAML was minified correctly
    assert result.text != yaml_text
    assert len(result.text) > 0
    assert "a:" in result.text


def test_drop_nulls_uses_ctx_parsed() -> None:
    """DropNullsStrategy reads ctx.parsed — no json.loads, returns parsed."""
    ctx = SmeltContext(parsed={"a": None, "b": 1})
    strategy = DropNullsStrategy()

    with patch("axm_smelt.strategies.drop_nulls.json.loads") as mock_loads:
        result = strategy.apply(ctx)

    mock_loads.assert_not_called()
    assert result.parsed == {"b": 1}


def test_flatten_chain_no_reparse() -> None:
    """Flatten then tabular on same ctx — json.loads never called."""
    data = [{"a": {"b": 1}}, {"a": {"b": 2}}]
    ctx = SmeltContext(parsed=data, format=Format.JSON)

    flatten = FlattenStrategy()
    tabular = TabularStrategy()

    with (
        patch("axm_smelt.strategies.flatten.json.loads") as mock_fl,
        patch("axm_smelt.strategies.tabular.json.loads") as mock_tl,
    ):
        mid = flatten.apply(ctx)
        _result = tabular.apply(mid)

    mock_fl.assert_not_called()
    mock_tl.assert_not_called()


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_aggressive_preset_single_parse() -> None:
    """Aggressive preset on JSON — json.loads called at most once."""
    big_json = json.dumps([{"name": "alice", "score": 3.14159, "extra": None}] * 20)
    real_loads = json.loads

    with patch("json.loads", wraps=real_loads) as mock_loads:
        smelt(big_json, preset="aggressive")

    assert mock_loads.call_count <= 1


def test_smelt_output_identical() -> None:
    """smelt output is deterministic — identical across two runs."""
    text = json.dumps({"users": [{"name": "Alice", "age": None, "score": 3.14159}]})
    r1 = smelt(text, preset="aggressive")
    r2 = smelt(text, preset="aggressive")

    assert r1.compacted == r2.compacted
    assert r1.savings_pct == r2.savings_pct


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_mixed_text_parsed_strategies() -> None:
    """strip_quotes (text) after drop_nulls (parsed) — lazy serialization."""
    data = {"key_a": "val", "key_b": None, "key_c": 42}
    ctx = SmeltContext(parsed=data, format=Format.JSON)

    drop = DropNullsStrategy()
    strip = StripQuotesStrategy()

    mid = drop.apply(ctx)
    result = strip.apply(mid)

    # Lazy serialization triggered before strip_quotes (text-level)
    assert "key_a" in result.text
    assert "key_b" not in result.text  # null was dropped


def test_non_json_through_aggressive() -> None:
    """Plain text through aggressive — all strategies skip gracefully."""
    plain = "This is just plain text, not JSON at all."
    result = smelt(plain, preset="aggressive")

    assert result.compacted == plain


def test_yaml_through_minify() -> None:
    """YAML input with format=YAML — minifies via _minify_yaml path."""
    yaml_text = "a: 1\nb: 2\nc: 3\n"
    ctx = SmeltContext(text=yaml_text, format=Format.YAML)
    strategy = MinifyStrategy()

    result = strategy.apply(ctx)

    assert result.text != yaml_text
    assert len(result.text) > 0
