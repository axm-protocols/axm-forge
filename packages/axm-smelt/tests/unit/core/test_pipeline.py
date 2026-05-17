from __future__ import annotations

import json
import textwrap
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from axm_smelt import smelt as _smelt_root
from axm_smelt.core.models import Format, SmeltContext, SmeltReport
from axm_smelt.core.pipeline import (
    check,
    resolve_input,
    resolve_strategies,
    smelt,
)
from axm_smelt.strategies import get_preset
from tests.unit._helpers import _fixture_text

# --- Functional tests ---


def test_smelt_json_minify() -> None:
    text = '{\n  "name": "Alice"\n}'
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    assert report.savings_pct > 0
    assert "minify" in report.strategies_applied


def test_smelt_with_preset() -> None:
    text = '{\n  "name": "Alice"\n}'
    report = smelt(text, preset="safe")
    assert isinstance(report, SmeltReport)
    assert "minify" in report.strategies_applied


def test_check_no_transform(sample_json: str) -> None:
    report = check(sample_json)
    assert isinstance(report, SmeltReport)
    assert report.original == report.compacted


def test_pipeline_preserves_data() -> None:
    text = '{\n  "name": "Alice",\n  "items": [1, 2, 3]\n}'
    report = smelt(text)
    assert json.loads(report.compacted) == json.loads(text)


# --- Edge cases ---


def test_smelt_empty_input() -> None:
    report = smelt("")
    assert isinstance(report, SmeltReport)
    assert report.original_tokens >= 0


def test_smelt_already_minified() -> None:
    report = smelt('{"a":1}')
    assert isinstance(report, SmeltReport)
    assert report.savings_pct == 0


def test_smelt_large_json() -> None:
    data = {f"key_{i}": f"value_{i}" for i in range(10000)}
    text = json.dumps(data, indent=2)
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    assert report.savings_pct > 0


def test_smelt_invalid_json_like_start() -> None:
    text = '{"broken": '
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    assert report.format == Format.TEXT


def test_smelt_unicode_content() -> None:
    text = json.dumps({"emoji": "\U0001f680", "cjk": "你好"}, indent=2)
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    content = json.loads(report.compacted)
    assert content["emoji"] == "\U0001f680"
    assert content["cjk"] == "你好"


def test_smelt_nested_json() -> None:
    nested: dict[str, Any] = {"level": 0}
    current: dict[str, Any] = nested
    for i in range(1, 12):
        current["child"] = {"level": i}
        current = current["child"]
    text = json.dumps(nested, indent=2)
    report = smelt(text)
    assert isinstance(report, SmeltReport)
    assert json.loads(report.compacted) == nested


# --- merged from test_aggressive_preset_uses_new_name.py ---


def test_aggressive_preset_uses_new_name() -> None:
    payload = json.dumps(
        {
            "items": [
                {"label": "a-very-long-repeated-value-string-payload"},
                {"label": "a-very-long-repeated-value-string-payload"},
                {"label": "a-very-long-repeated-value-string-payload"},
            ]
        }
    )
    report = smelt(payload, preset="aggressive")
    applied = getattr(report, "strategies_applied", None) or getattr(
        report, "applied", []
    )
    assert "dedup_values" not in applied


# --- merged from test_check_unchanged.py ---


def test_check_unchanged() -> None:
    report = check(_fixture_text())
    assert isinstance(report.strategy_estimates, dict)
    assert report.strategy_estimates


# --- merged from test_pipeline_smelt_unchanged.py ---


def test_pipeline_smelt_unchanged() -> None:
    text = _fixture_text()
    report = smelt(text)
    assert report.compacted_tokens <= report.original_tokens
    assert isinstance(report.strategies_applied, list)
    assert report.strategies_applied, "expected at least one strategy applied"


# --- merged from test_pipeline_presets.py ---


class TestSmeltPresets:
    def test_smelt_preset_moderate(self) -> None:
        data = json.dumps(
            [{"name": f"item_{i}", "value": i, "active": True} for i in range(20)]
        )
        report = smelt(data, preset="moderate")
        assert report.savings_pct > 0
        assert "minify" in report.strategies_applied
        assert "tabular" in report.strategies_applied

    def test_smelt_strategies_list(self) -> None:
        data = json.dumps([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
        report = smelt(data, strategies=["tabular"])
        assert report.strategies_applied == ["tabular"]

    def test_tabular_token_savings(self) -> None:
        data = json.dumps(
            [{"name": f"person_{i}", "age": 20 + i, "city": "Paris"} for i in range(50)]
        )
        report = smelt(data, strategies=["tabular"])
        assert report.savings_pct >= 30

    # -- Unit tests: preset composition --

    def test_safe_preset_includes_collapse(self) -> None:
        strats = get_preset("safe")
        names = [s.name for s in strats]
        assert "collapse_whitespace" in names

    def test_moderate_preset_includes_markdown(self) -> None:
        strats = get_preset("moderate")
        names = [s.name for s in strats]
        assert "compact_tables" in names
        assert "strip_html_comments" in names

    def test_aggressive_preset_includes_all_markdown(self) -> None:
        strats = get_preset("aggressive")
        names = [s.name for s in strats]
        assert "collapse_whitespace" in names
        assert "compact_tables" in names
        assert "strip_html_comments" in names

    # -- Functional tests: markdown through pipeline --

    def test_smelt_markdown_safe_preset(self) -> None:
        md = "# Title\n\n\n\n\nParagraph one.\n\n\n\n\nParagraph two.\n\n\n\n"
        report = smelt(md, preset="safe")
        assert "collapse_whitespace" in report.strategies_applied
        assert len(report.compacted) < len(report.original)

    def test_smelt_markdown_moderate_preset(self) -> None:
        md = textwrap.dedent("""\
            # Report

            <!-- TODO: remove this -->
            <!-- draft notes -->

            |  Name   |  Age  |  City   |
            | ------- | ----- | ------- |
            |  Alice  |  30   |  Paris  |
            |  Bob    |  25   |  Lyon   |




            End.
        """)
        report = smelt(md, preset="moderate")
        assert "collapse_whitespace" in report.strategies_applied
        assert "compact_tables" in report.strategies_applied
        assert "strip_html_comments" in report.strategies_applied

    def test_smelt_json_with_markdown_presets(self) -> None:
        data = json.dumps([{"name": "x", "value": 1}, {"name": "y", "value": 2}])
        report = smelt(data, preset="moderate")
        # Markdown strategies are noop on JSON — only JSON strategies apply
        assert "collapse_whitespace" not in report.strategies_applied
        assert "compact_tables" not in report.strategies_applied
        assert "strip_html_comments" not in report.strategies_applied
        # JSON strategies still work
        assert "minify" in report.strategies_applied

    # -- Edge cases --

    def test_strategy_ordering_whitespace_before_tables(self) -> None:
        md = textwrap.dedent("""\
            # Data




            |  Col A  |  Col B  |
            | ------- | ------- |
            |  1      |  2      |
        """)
        report = smelt(md, preset="moderate")
        applied = report.strategies_applied
        assert "collapse_whitespace" in applied
        assert "compact_tables" in applied
        idx_ws = applied.index("collapse_whitespace")
        idx_ct = applied.index("compact_tables")
        assert idx_ws < idx_ct

    def test_check_markdown_reports_all_strategies(self) -> None:
        md = textwrap.dedent("""\
            # Project Setup

            <!-- internal note -->

            |  Tool   |  Version  |
            | ------- | --------- |
            |  ruff   |  0.15     |




            Done.
        """)
        report = check(md)
        strategy_names = list(report.strategy_estimates.keys())
        assert "collapse_whitespace" in strategy_names
        assert "compact_tables" in strategy_names
        assert "strip_html_comments" in strategy_names


class TestSmeltEdgeCases:
    def test_unknown_preset(self) -> None:
        with pytest.raises(ValueError, match="Unknown preset"):
            smelt("{}", preset="invalid")

    def test_unknown_strategy(self) -> None:
        with pytest.raises(ValueError, match="Unknown strategy"):
            smelt("{}", strategies=["nonexistent"])


# --- merged from test_parsed_input.py ---


def test_smelt_with_parsed_dict() -> None:
    """smelt(parsed=dict) returns a valid SmeltReport with minified JSON."""
    parsed = {"a": 1, "b": [1, 2, 3]}
    report = smelt(parsed=parsed)

    assert report.compacted is not None
    assert report.original_tokens > 0
    assert report.compacted_tokens > 0
    reparsed = json.loads(report.compacted)
    assert reparsed == parsed or isinstance(reparsed, dict)


def test_smelt_tool_dict_no_dumps(mocker: MockerFixture) -> None:
    """SmeltTool.execute(data=dict) must NOT json.dumps before pipeline entry."""
    from axm_smelt.tools.smelt import SmeltTool

    spy = mocker.patch(
        "axm_smelt.tools.smelt.json.dumps",
        side_effect=AssertionError("json.dumps should not be called"),
    )

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
    parsed = {"x": [1, 2, 3]}
    report = check(parsed=parsed)

    assert report.format.value == "json"
    assert report.original_tokens > 0


def test_check_neither_text_nor_parsed_raises() -> None:
    """check() with no input raises ValueError."""
    with pytest.raises(ValueError):
        check()


# --- merged from test_resolve_helpers.py ---


def test_resolve_input_text_only() -> None:
    text, parsed = resolve_input(text="hello", parsed=None)
    assert text == "hello"
    assert parsed is None


def test_resolve_input_parsed_dict() -> None:
    data = {"a": 1}
    text, parsed = resolve_input(text=None, parsed=data)
    assert text == json.dumps(data, separators=(",", ":"))
    assert parsed is data


def test_resolve_input_neither() -> None:
    with pytest.raises(ValueError, match="Either text or parsed must be provided"):
        resolve_input(text=None, parsed=None)


def test_resolve_input_parsed_overrides_text() -> None:
    """When both text and parsed are provided, parsed takes precedence."""
    data = {"key": "value"}
    text, parsed = resolve_input(text="ignored", parsed=data)
    assert text == json.dumps(data, separators=(",", ":"))
    assert parsed is data


def test_resolve_input_parsed_list() -> None:
    data = [1, 2, 3]
    text, parsed = resolve_input(text=None, parsed=data)
    assert text == json.dumps(data, separators=(",", ":"))
    assert parsed is data


def test_resolve_strategies_explicit() -> None:
    strats = resolve_strategies(["minify"], None)
    assert len(strats) == 1
    assert strats[0].name == "minify"


def test_resolve_strategies_preset() -> None:
    strats = resolve_strategies(None, "safe")
    expected = get_preset("safe")
    assert [s.name for s in strats] == [s.name for s in expected]


def test_resolve_strategies_default() -> None:
    """No strategies and no preset falls back to safe preset."""
    strats = resolve_strategies(None, None)
    expected = get_preset("safe")
    assert [s.name for s in strats] == [s.name for s in expected]


def test_smelt_zero_token_input() -> None:
    report = smelt(text="")
    assert report.savings_pct == 0.0
    assert report.original == ""
    assert report.compacted_tokens >= 0


def test_smelt_all_strategies_regress_minify_only() -> None:
    """When every strategy increases tokens, original text is returned."""
    text = "a"
    report = smelt(text=text, strategies=["minify"])
    assert report.compacted == text or report.strategies_applied == []


# --- merged from test_strategies_functional.py ---


def _complex_json() -> str:
    """JSON blob that triggers all strategy types."""
    return json.dumps(
        {
            "wrapper": {
                "data": [
                    {"name": "Alice", "score": 3.14159, "notes": None},
                    {"name": "Bob", "score": 2.71828, "notes": ""},
                ]
            },
            "empty": {},
            "nested_single": {"inner": {"value": 1}},
        },
        indent=2,
    )


def test_aggressive_preset_all_strategies() -> None:
    result = smelt(_complex_json(), preset="aggressive")
    assert result.savings_pct > 0
    assert len(result.strategies_applied) == 6


def test_check_strategy_estimates() -> None:
    data = json.dumps(
        {
            "a": {"b": 1},
            "c": None,
            "d": 3.14159,
        }
    )
    report = check(data)
    assert hasattr(report, "strategy_estimates")
    assert isinstance(report.strategy_estimates, dict)
    positive = {k: v for k, v in report.strategy_estimates.items() if v > 0}
    assert len(positive) > 0


def test_moderate_preset_with_drop_nulls() -> None:
    data = json.dumps({"a": 1, "b": None, "c": "", "d": []})
    result = smelt(data, preset="moderate")
    assert "drop_nulls" in result.strategies_applied


# --- merged from test_token_guard.py ---


class _FakeStrategy:
    """Fake strategy that returns fixed output text."""

    def __init__(self, name: str, output_text: str) -> None:
        self.name = name
        self._output_text = output_text

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        return SmeltContext(text=self._output_text, format=ctx.format)


def test_guard_rejects_regression(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategy that increases tokens must be rejected."""
    from axm_smelt.core import pipeline

    original = "short text"
    bloated = "this is a much longer text that has many more tokens than the original"

    fake = _FakeStrategy("bloater", bloated)
    monkeypatch.setattr(pipeline, "get_strategy", lambda name: fake)

    report = pipeline.smelt(text=original, strategies=["bloater"])

    assert "bloater" not in report.strategies_applied
    assert report.compacted == original


def test_guard_accepts_improvement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategy that reduces tokens must be accepted."""
    from axm_smelt.core import pipeline

    original = '{"key":   "value",   "another":   "thing"}'
    compact = '{"key":"value","another":"thing"}'

    fake = _FakeStrategy("minifier", compact)
    monkeypatch.setattr(pipeline, "get_strategy", lambda name: fake)

    report = pipeline.smelt(text=original, strategies=["minifier"])

    assert "minifier" in report.strategies_applied
    assert report.compacted == compact


def test_check_hides_negative_estimates() -> None:
    """check() must not include strategies with negative savings."""
    text = "| a | b |\n|---|---|\n| c | d |\n"

    report = check(text)

    for strat, pct in report.strategy_estimates.items():
        assert pct > 0, f"{strat} has non-positive estimate {pct}"


def test_claude_md_no_regression() -> None:
    """smelt with compact_tables on table-heavy markdown must not regress."""
    claude_md = (
        "# Project\n\n"
        "| Column A | Column B | Column C |\n"
        "|----------|----------|----------|\n"
        "| value 1  | value 2  | value 3  |\n"
        "| value 4  | value 5  | value 6  |\n\n"
        "Some text after the table.\n\n"
        "| Name | Description | Notes |\n"
        "|------|-------------|-------|\n"
        "| foo  | A thing     | OK    |\n"
        "| bar  | Another     | Fine  |\n"
    )

    report = smelt(text=claude_md, strategies=["compact_tables"])

    assert report.savings_pct >= 0.0
    assert report.compacted_tokens <= report.original_tokens


def test_pipeline_cumulative_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """One regressing strategy mid-pipeline must not affect the others."""
    from axm_smelt.core import pipeline

    original = "some   padded   text   with   extra   spaces   everywhere"
    improved = "some padded text with extra spaces everywhere"
    bloated = improved + " and extra bloat added here unnecessarily for no reason"

    fake_good = _FakeStrategy("compactor", improved)
    fake_bad = _FakeStrategy("bloater", bloated)

    strategy_map = {"compactor": fake_good, "bloater": fake_bad}
    monkeypatch.setattr(pipeline, "get_strategy", lambda name: strategy_map[name])

    report = pipeline.smelt(text=original, strategies=["compactor", "bloater"])

    assert "compactor" in report.strategies_applied
    assert "bloater" not in report.strategies_applied
    assert report.compacted_tokens <= report.original_tokens


def test_zero_token_change_discarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strategy that changes text but keeps same token count is discarded."""
    from axm_smelt.core import pipeline

    original = "hello world"
    changed = "world hello"

    fixed_count = 10
    monkeypatch.setattr(pipeline, "count", lambda text, **kw: fixed_count)

    fake = _FakeStrategy("shuffler", changed)
    monkeypatch.setattr(pipeline, "get_strategy", lambda name: fake)

    report = pipeline.smelt(text=original, strategies=["shuffler"])

    assert "shuffler" not in report.strategies_applied
    assert report.compacted == original


def test_all_strategies_regress(monkeypatch: pytest.MonkeyPatch) -> None:
    """When all strategies regress, output equals input."""
    from axm_smelt.core import pipeline

    original = "short"
    bloated_1 = "this is significantly longer than the original text was before"
    bloated_2 = "and this is also much much longer than the original input text"

    strategy_map = {
        "bad1": _FakeStrategy("bad1", bloated_1),
        "bad2": _FakeStrategy("bad2", bloated_2),
    }
    monkeypatch.setattr(pipeline, "get_strategy", lambda name: strategy_map[name])

    report = pipeline.smelt(text=original, strategies=["bad1", "bad2"])

    assert report.strategies_applied == []
    assert report.compacted == original


# --- merged from test_zero_reparse.py ---


def test_minify_uses_ctx_format() -> None:
    """MinifyStrategy reads ctx.format instead of calling detect_format."""
    from unittest.mock import patch

    from axm_smelt.strategies.minify import MinifyStrategy

    yaml_text = "a: 1\nb: 2\nc: 3\n"
    ctx = SmeltContext(text=yaml_text, format=Format.YAML)
    strategy = MinifyStrategy()

    with patch("axm_smelt.strategies.minify.detect_format") as mock_detect:
        result = strategy.apply(ctx)

    mock_detect.assert_not_called()
    assert result.text != yaml_text
    assert len(result.text) > 0
    assert "a:" in result.text


def test_drop_nulls_uses_ctx_parsed() -> None:
    """DropNullsStrategy reads ctx.parsed — no json.loads, returns parsed."""
    from unittest.mock import patch

    from axm_smelt.strategies.drop_nulls import DropNullsStrategy

    ctx = SmeltContext(parsed={"a": None, "b": 1})
    strategy = DropNullsStrategy()

    with patch("axm_smelt.strategies.drop_nulls.json.loads") as mock_loads:
        result = strategy.apply(ctx)

    mock_loads.assert_not_called()
    assert result.parsed == {"b": 1}


def test_flatten_chain_no_reparse() -> None:
    """Flatten then tabular on same ctx — json.loads never called."""
    from unittest.mock import patch

    from axm_smelt.strategies.flatten import FlattenStrategy
    from axm_smelt.strategies.tabular import TabularStrategy

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


def test_aggressive_preset_single_parse() -> None:
    """Aggressive preset on JSON — json.loads called at most once."""
    from unittest.mock import patch

    big_json = json.dumps([{"name": "alice", "score": 3.14159, "extra": None}] * 20)
    real_loads = json.loads

    with patch("json.loads", wraps=real_loads) as mock_loads:
        _smelt_root(big_json, preset="aggressive")

    assert mock_loads.call_count <= 1


def test_smelt_output_identical() -> None:
    """smelt output is deterministic — identical across two runs."""
    text = json.dumps({"users": [{"name": "Alice", "age": None, "score": 3.14159}]})
    r1 = _smelt_root(text, preset="aggressive")
    r2 = _smelt_root(text, preset="aggressive")

    assert r1.compacted == r2.compacted
    assert r1.savings_pct == r2.savings_pct


def test_mixed_text_parsed_strategies() -> None:
    """strip_quotes (text) after drop_nulls (parsed) — lazy serialization."""
    from axm_smelt.strategies.drop_nulls import DropNullsStrategy
    from axm_smelt.strategies.strip_quotes import StripQuotesStrategy

    data = {"key_a": "val", "key_b": None, "key_c": 42}
    ctx = SmeltContext(parsed=data, format=Format.JSON)

    drop = DropNullsStrategy()
    strip = StripQuotesStrategy()

    mid = drop.apply(ctx)
    result = strip.apply(mid)

    assert "key_a" in result.text
    assert "key_b" not in result.text  # null was dropped


def test_non_json_through_aggressive() -> None:
    """Plain text through aggressive — all strategies skip gracefully."""
    plain = "This is just plain text, not JSON at all."
    result = _smelt_root(plain, preset="aggressive")

    assert result.compacted == plain


def test_yaml_through_minify() -> None:
    """YAML input with format=YAML — minifies via _minify_yaml path."""
    from axm_smelt.strategies.minify import MinifyStrategy

    yaml_text = "a: 1\nb: 2\nc: 3\n"
    ctx = SmeltContext(text=yaml_text, format=Format.YAML)
    strategy = MinifyStrategy()

    result = strategy.apply(ctx)

    assert result.text != yaml_text
    assert len(result.text) > 0
