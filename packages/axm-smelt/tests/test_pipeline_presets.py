from __future__ import annotations

import json
import textwrap

import pytest

from axm_smelt.core.pipeline import check, smelt
from axm_smelt.strategies import get_preset


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
