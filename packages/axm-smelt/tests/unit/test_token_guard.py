from __future__ import annotations

import pytest

from axm_smelt.core.models import SmeltContext


class _FakeStrategy:
    """Fake strategy that returns fixed output text."""

    def __init__(self, name: str, output_text: str) -> None:
        self.name = name
        self._output_text = output_text

    def apply(self, ctx: SmeltContext) -> SmeltContext:
        return SmeltContext(text=self._output_text, format=ctx.format)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


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
    from axm_smelt.core.pipeline import check

    # Markdown table — compact_tables may regress on small tables
    text = "| a | b |\n|---|---|\n| c | d |\n"

    report = check(text)

    for strat, pct in report.strategy_estimates.items():
        assert pct > 0, f"{strat} has non-positive estimate {pct}"


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_claude_md_no_regression() -> None:
    """smelt with compact_tables on table-heavy markdown must not regress."""
    from axm_smelt.core.pipeline import smelt

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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


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
