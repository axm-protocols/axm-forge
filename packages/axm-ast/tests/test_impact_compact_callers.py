"""Tests for _format_callers_compact refactoring: prod/test separation and grouping."""

from __future__ import annotations

import re

from axm_ast.tools.impact import _format_callers_compact


def _caller(module: str, line: int) -> dict[str, str | int]:
    """Build a minimal caller dict."""
    return {"module": module, "line": line, "context": "", "call_expression": ""}


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestProdCallersShownWithLines:
    def test_prod_callers_shown_with_lines(self) -> None:
        callers = [
            _caller("src.axm_ast.tools.impact", 116),
            _caller("src.axm_ast.hooks.impact", 163),
            _caller("tests.test_tools", 42),
            _caller("tests.test_impact_compact", 62),
            _caller("tests.test_impact_compact", 103),
        ]
        result = _format_callers_compact(callers, symbol_module="source_body")
        assert "Prod:" in result
        assert "src.axm_ast.tools.impact:116" in result
        assert "src.axm_ast.hooks.impact:163" in result


class TestTestCallersGroupedByFile:
    def test_test_callers_grouped_by_file(self) -> None:
        callers = [
            _caller("tests.test_foo", 10),
            _caller("tests.test_foo", 20),
            _caller("tests.test_foo", 30),
            _caller("tests.test_foo", 40),
            _caller("tests.test_foo", 50),
        ]
        result = _format_callers_compact(callers, symbol_module="bar")
        # Indirect test (test_foo doesn't contain "bar")
        assert "test_foo" in result
        assert "\u00d75" in result  # x5
        assert re.search(r"\d+,\d+", result)


class TestLinesCappedAt5ForIndirect:
    def test_lines_capped_at_5_for_indirect(self) -> None:
        callers = [_caller("tests.test_foo", i) for i in range(1, 9)]
        result = _format_callers_compact(callers, symbol_module="bar")
        assert "\u00d78" in result  # x8
        assert re.search(r"\d+,\d+", result)
        assert "\u2026" in result  # …


class TestLinesNotCappedForDirect:
    def test_lines_not_capped_for_direct(self) -> None:
        callers = [_caller("tests.test_source_body", i) for i in range(1, 9)]
        result = _format_callers_compact(callers, symbol_module="source_body")
        # Direct test — all 8 lines shown, no …
        for i in range(1, 9):
            assert str(i) in result
        assert "\u2026" not in result


class TestDirectVsIndirectClassification:
    def test_direct_vs_indirect_classification(self) -> None:
        callers = [
            _caller("tests.test_source_body", 10),
            _caller("tests.test_tools", 20),
        ]
        result = _format_callers_compact(callers, symbol_module="source_body")
        # test_source_body is direct (contains "source_body")
        # test_tools is indirect
        assert "Direct" in result or "direct" in result.lower()
        assert "test_source_body" in result
        assert "test_tools" in result


class TestNoCallersReturnsDash:
    def test_no_callers_returns_dash(self) -> None:
        result = _format_callers_compact([], symbol_module="foo")
        assert result == "\u2014"


class TestProdOnlyNoTestSection:
    def test_prod_only_no_test_section(self) -> None:
        callers = [
            _caller("src.axm_ast.tools.impact", 116),
            _caller("src.axm_ast.hooks.impact", 163),
        ]
        result = _format_callers_compact(callers, symbol_module="impact")
        assert "Prod:" in result
        assert "Tests:" not in result
        assert "Direct" not in result
        assert "Indirect" not in result


class TestTestOnlyNoProdSection:
    def test_test_only_no_prod_section(self) -> None:
        callers = [
            _caller("tests.test_foo", 10),
            _caller("tests.test_foo", 20),
        ]
        result = _format_callers_compact(callers, symbol_module="bar")
        assert "Prod:" not in result
        assert "Tests:" in result or "Indirect" in result


class TestSmallTestFileShowsAllLines:
    def test_small_test_file_shows_all_lines(self) -> None:
        callers = [
            _caller("tests.test_foo", 3),
            _caller("tests.test_foo", 5),
            _caller("tests.test_foo", 7),
        ]
        result = _format_callers_compact(callers, symbol_module="bar")
        assert "3,5,7" in result
        assert "\u2026" not in result
        # No xN prefix when <=5
        assert "\u00d7" not in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestNoSymbolModule:
    def test_no_symbol_module_treats_all_as_indirect(self) -> None:
        callers = [
            _caller("tests.test_source_body", 1),
            _caller("tests.test_source_body", 2),
            _caller("tests.test_source_body", 3),
            _caller("tests.test_source_body", 4),
            _caller("tests.test_source_body", 5),
            _caller("tests.test_source_body", 6),
            _caller("tests.test_source_body", 7),
            _caller("tests.test_source_body", 8),
        ]
        result = _format_callers_compact(callers, symbol_module=None)
        # All treated as indirect → capped at 5
        assert "1,2,3,4,5" in result
        assert "\u2026" in result


class TestSingleCaller:
    def test_single_caller(self) -> None:
        callers = [_caller("src.axm_ast.cli", 42)]
        result = _format_callers_compact(callers, symbol_module="impact")
        assert "Prod: src.axm_ast.cli:42" in result
        assert "Tests:" not in result
        assert "Direct" not in result


class TestModuleNameAmbiguity:
    def test_module_name_ambiguity(self) -> None:
        callers = [
            _caller("tests.test_impact", 10),
            _caller("tests.test_impact_compact", 20),
        ]
        result = _format_callers_compact(callers, symbol_module="impact")
        # Both test_impact and test_impact_compact contain "impact"
        # → both classified as direct
        assert "test_impact" in result
        assert "test_impact_compact" in result
