"""Tests for axm_ast.tools.impact.

Merged canonical mirror covering the public/internal surface of
``axm_ast.tools.impact``: batch compact formatting, single/multi compact
output, the ``_format_callers_compact`` helper, edge cases on ``ImpactTool``,
failure logging, the text render path, and severity/score handling.
"""

from __future__ import annotations

import logging
import re
from typing import Any, cast

import pytest

from axm_ast.core.impact import ImpactResult
from axm_ast.tools.impact import (
    ImpactTool,
    _format_callers_compact,
    format_impact_compact,
    format_impact_compact_multi,
    render_impact_batch_text,
    render_impact_text,
)
from axm_ast.tools.impact_text import _render_impact_single

# ── batch compact ──


def _bc_make_report(
    symbol: str,
    score: str | None = None,
    *,
    module: str = "mod",
    line: int = 1,
    callers: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    report: dict[str, object] = {
        "symbol": symbol,
        "definition": {"module": module, "line": line, "file": f"{module}.py"},
        "callers": callers or [],
        "test_files": [],
    }
    if score is not None:
        report["score"] = score
    return report


def test_batch_compact_per_symbol_scores() -> None:
    """3 reports with HIGH, LOW, MEDIUM - each row shows its own score."""
    reports = [
        _bc_make_report("func_a", "HIGH"),
        _bc_make_report("func_b", "LOW"),
        _bc_make_report("func_c", "MEDIUM"),
    ]
    result = format_impact_compact_multi(reports, score="HIGH")
    rows = [
        line
        for line in result.splitlines()
        if line.startswith("|") and "---" not in line and "Symbol" not in line
    ]
    assert len(rows) == 3
    assert "HIGH" in rows[0]
    assert "LOW" in rows[1]
    assert "MEDIUM" in rows[2]


def test_batch_compact_all_same_score() -> None:
    """2 reports both LOW - both rows show LOW."""
    reports = [
        _bc_make_report("alpha", "LOW"),
        _bc_make_report("beta", "LOW"),
    ]
    result = format_impact_compact_multi(reports, score="LOW")
    rows = [
        line
        for line in result.splitlines()
        if line.startswith("|") and "---" not in line and "Symbol" not in line
    ]
    assert len(rows) == 2
    for row in rows:
        assert "LOW" in row


def test_batch_compact_missing_score_defaults_to_low() -> None:
    """Report with no 'score' key should display LOW as default."""
    reports = [
        _bc_make_report("no_score_sym"),
    ]
    result = format_impact_compact_multi(reports, score="LOW")
    rows = [
        line
        for line in result.splitlines()
        if line.startswith("|") and "---" not in line and "Symbol" not in line
    ]
    assert len(rows) == 1
    assert "LOW" in rows[0]


def test_batch_compact_single_symbol() -> None:
    """Single-symbol batch shows its own score in the row."""
    reports = [
        _bc_make_report("only_one", "MEDIUM"),
    ]
    result = format_impact_compact_multi(reports, score="MEDIUM")
    rows = [
        line
        for line in result.splitlines()
        if line.startswith("|") and "---" not in line and "Symbol" not in line
    ]
    assert len(rows) == 1
    assert "MEDIUM" in rows[0]


# ── compact format ──


def _cf_make_impact_dict(
    symbol: str = "greet",
    *,
    callers: list[dict[str, Any]] | None = None,
    test_files: list[str] | None = None,
    definition: dict[str, Any] | None = None,
    score: str = "MEDIUM",
) -> dict[str, Any]:
    """Build a realistic impact analysis dict."""
    return {
        "symbol": symbol,
        "definition": definition
        or {"module": "demo.core", "line": 10, "kind": "function"},
        "callers": callers or [],
        "type_refs": [],
        "reexports": [],
        "affected_modules": ["demo.core", "demo.cli"],
        "test_files": test_files or [],
        "git_coupled": [],
        "score": score,
    }


class TestFormatImpactCompactSingle:
    """Single-symbol compact formatting."""

    def test_format_impact_compact_single(self) -> None:
        """1 definition + 3 callers → table row + caller summary."""
        impact = _cf_make_impact_dict(
            symbol="greet",
            callers=[
                {"name": "main", "module": "demo.cli", "line": 10},
                {"name": "run", "module": "demo.app", "line": 20},
                {"name": "test_greet", "module": "tests.test_core"},
            ],
        )
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "Symbol" in result
        assert "Score" in result
        assert "greet" in result
        assert "demo.core:10" in result
        assert "MEDIUM" in result
        assert "Prod" in result
        assert "demo.cli:10" in result
        assert "demo.app:20" in result
        assert "test_core" in result


class TestFormatImpactCompactMulti:
    """Multi-symbol (merged) compact formatting."""

    def test_format_impact_compact_multi(self) -> None:
        """List of 4 reports → table with 4 per-symbol rows."""
        reports = [
            _cf_make_impact_dict(
                symbol=sym,
                definition={"module": mod, "line": ln, "kind": "function"},
                callers=[{"name": "x", "module": "mod_x"}],
            )
            for sym, mod, ln in [
                ("A", "mod_a", 1),
                ("B", "mod_b", 5),
                ("C", "mod_c", 10),
                ("D", "mod_d", 20),
            ]
        ]
        result = format_impact_compact(reports)
        assert isinstance(result, str)
        assert "mod_a" in result
        assert "mod_b" in result
        assert "mod_c" in result
        assert "mod_d" in result
        assert "MEDIUM" in result


class TestFormatImpactCompactNoCallers:
    """Compact formatting when no callers exist."""

    def test_format_impact_compact_no_callers(self) -> None:
        """Symbol with 0 callers → table shows em-dash for callers."""
        impact = _cf_make_impact_dict(symbol="lonely", callers=[], score="LOW")
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "—" in result  # em-dash = no callers
        assert "lonely" in result


class TestFormatImpactCompactTestExposure:
    """Compact formatting with test file exposure."""

    def test_format_impact_compact_test_exposure(self) -> None:
        """Dict with test_files → footer lists file names."""
        impact = _cf_make_impact_dict(
            test_files=["test_core.py", "test_cli.py", "test_integration.py"],
        )
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "test_core.py" in result
        assert "test_cli.py" in result
        assert "test_integration.py" in result


class TestImpactCompactEdgeCases:
    """Edge cases for compact output mode."""

    def test_symbol_not_found(self) -> None:
        """Unknown symbol → row with 'not found' indicator."""
        impact: dict[str, Any] = {
            "symbol": "missing_func",
            "definition": None,
            "callers": [],
            "type_refs": [],
            "reexports": [],
            "affected_modules": [],
            "test_files": [],
            "git_coupled": [],
            "score": "LOW",
            "error": "Symbol 'missing_func' not found",
        }
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "not found" in result.lower() or "missing_func" in result

    def test_no_test_files(self) -> None:
        """Symbol with no tests → footer says 'no test coverage'."""
        impact = _cf_make_impact_dict(test_files=[])
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "no test coverage" in result


# ── _format_callers_compact ──


def _fc_caller(module: str, line: int) -> dict[str, str | int]:
    """Build a minimal caller dict."""
    return {"module": module, "line": line, "context": "", "call_expression": ""}


class TestProdCallersShownWithLines:
    def test_prod_callers_shown_with_lines(self) -> None:
        callers = [
            _fc_caller("src.axm_ast.tools.impact", 116),
            _fc_caller("src.axm_ast.hooks.impact", 163),
            _fc_caller("tests.test_tools", 42),
            _fc_caller("tests.test_impact_compact", 62),
            _fc_caller("tests.test_impact_compact", 103),
        ]
        result = _format_callers_compact(callers, symbol_module="source_body")
        assert "Prod:" in result
        assert "src.axm_ast.tools.impact:116" in result
        assert "src.axm_ast.hooks.impact:163" in result


class TestTestCallersGroupedByFile:
    def test_test_callers_grouped_by_file(self) -> None:
        callers = [
            _fc_caller("tests.test_foo", 10),
            _fc_caller("tests.test_foo", 20),
            _fc_caller("tests.test_foo", 30),
            _fc_caller("tests.test_foo", 40),
            _fc_caller("tests.test_foo", 50),
        ]
        result = _format_callers_compact(callers, symbol_module="bar")
        assert "test_foo" in result
        assert "×5" in result  # x5  # noqa: RUF001
        assert re.search(r"\d+,\d+", result)


class TestLinesCappedAt5ForIndirect:
    def test_lines_capped_at_5_for_indirect(self) -> None:
        callers = [_fc_caller("tests.test_foo", i) for i in range(1, 9)]
        result = _format_callers_compact(callers, symbol_module="bar")
        assert "×8" in result  # x8  # noqa: RUF001
        assert re.search(r"\d+,\d+", result)
        assert "…" in result  # …


class TestLinesNotCappedForDirect:
    def test_lines_not_capped_for_direct(self) -> None:
        callers = [_fc_caller("tests.test_source_body", i) for i in range(1, 9)]
        result = _format_callers_compact(callers, symbol_module="source_body")
        for i in range(1, 9):
            assert str(i) in result
        assert "…" not in result


class TestDirectVsIndirectClassification:
    def test_direct_vs_indirect_classification(self) -> None:
        callers = [
            _fc_caller("tests.test_source_body", 10),
            _fc_caller("tests.test_tools", 20),
        ]
        result = _format_callers_compact(callers, symbol_module="source_body")
        assert "Direct" in result or "direct" in result.lower()
        assert "test_source_body" in result
        assert "test_tools" in result


class TestNoCallersReturnsDash:
    def test_no_callers_returns_dash(self) -> None:
        result = _format_callers_compact([], symbol_module="foo")
        assert result == "—"


class TestProdOnlyNoTestSection:
    def test_prod_only_no_test_section(self) -> None:
        callers = [
            _fc_caller("src.axm_ast.tools.impact", 116),
            _fc_caller("src.axm_ast.hooks.impact", 163),
        ]
        result = _format_callers_compact(callers, symbol_module="impact")
        assert "Prod:" in result
        assert "Tests:" not in result
        assert "Direct" not in result
        assert "Indirect" not in result


class TestTestOnlyNoProdSection:
    def test_test_only_no_prod_section(self) -> None:
        callers = [
            _fc_caller("tests.test_foo", 10),
            _fc_caller("tests.test_foo", 20),
        ]
        result = _format_callers_compact(callers, symbol_module="bar")
        assert "Prod:" not in result
        assert "Tests:" in result or "Indirect" in result


class TestSmallTestFileShowsAllLines:
    def test_small_test_file_shows_all_lines(self) -> None:
        callers = [
            _fc_caller("tests.test_foo", 3),
            _fc_caller("tests.test_foo", 5),
            _fc_caller("tests.test_foo", 7),
        ]
        result = _format_callers_compact(callers, symbol_module="bar")
        assert "3,5,7" in result
        assert "…" not in result
        assert "×" not in result  # noqa: RUF001


class TestNoSymbolModule:
    def test_no_symbol_module_treats_all_as_indirect(self) -> None:
        callers = [
            _fc_caller("tests.test_source_body", 1),
            _fc_caller("tests.test_source_body", 2),
            _fc_caller("tests.test_source_body", 3),
            _fc_caller("tests.test_source_body", 4),
            _fc_caller("tests.test_source_body", 5),
            _fc_caller("tests.test_source_body", 6),
            _fc_caller("tests.test_source_body", 7),
            _fc_caller("tests.test_source_body", 8),
        ]
        result = _format_callers_compact(callers, symbol_module=None)
        assert "1,2,3,4,5" in result
        assert "…" in result


class TestSingleCaller:
    def test_single_caller(self) -> None:
        callers = [_fc_caller("src.axm_ast.cli", 42)]
        result = _format_callers_compact(callers, symbol_module="impact")
        assert "Prod: src.axm_ast.cli:42" in result
        assert "Tests:" not in result
        assert "Direct" not in result


class TestModuleNameAmbiguity:
    def test_module_name_ambiguity(self) -> None:
        callers = [
            _fc_caller("tests.test_impact", 10),
            _fc_caller("tests.test_impact_compact", 20),
        ]
        result = _format_callers_compact(callers, symbol_module="impact")
        assert "test_impact" in result
        assert "test_impact_compact" in result


# ── multi-symbol compact ──


def _ms_make_report(symbol: str, **overrides: object) -> dict[str, Any]:
    """Build a minimal single-symbol impact report.

    Keyword args: module, line, score, callers, test_files, error.
    """
    error = overrides.get("error")
    score = str(overrides.get("score", "LOW"))
    if error:
        return {"symbol": symbol, "error": error, "score": score}
    return {
        "symbol": symbol,
        "definition": {
            "module": overrides.get("module", "mod"),
            "line": overrides.get("line", 10),
        },
        "score": score,
        "callers": overrides.get("callers") or [],
        "test_files": overrides.get("test_files") or [],
    }


def _ms_caller(name: str, module: str, line: int) -> dict[str, Any]:
    return {"name": name, "module": module, "line": line}


def _ms_data_rows(text: str) -> list[str]:
    """Extract table data rows (skip header + separator)."""
    lines = text.strip().splitlines()
    return [ln for ln in lines if ln.startswith("|") and "---" not in ln][1:]


class TestMultiSymbolPerSymbolCallers:
    """AC1: each symbol row shows only its own callers."""

    def test_multi_symbol_per_symbol_callers(self) -> None:
        reports = [
            _ms_make_report(
                "func_a",
                module="pkg.a",
                line=1,
                callers=[_ms_caller("x", "pkg.x", 10)],
            ),
            _ms_make_report(
                "func_b",
                module="pkg.b",
                line=2,
                callers=[_ms_caller("y", "pkg.y", 20)],
            ),
            _ms_make_report(
                "func_c",
                module="pkg.c",
                line=3,
                callers=[_ms_caller("z", "pkg.z", 30)],
            ),
        ]
        result = format_impact_compact(reports)
        rows = _ms_data_rows(result)
        assert len(rows) == 3

        assert "pkg.x:10" in rows[0]
        assert "pkg.y" not in rows[0]
        assert "pkg.z" not in rows[0]

        assert "pkg.y:20" in rows[1]
        assert "pkg.x" not in rows[1]

        assert "pkg.z:30" in rows[2]
        assert "pkg.x" not in rows[2]


class TestMultiSymbolPerSymbolScores:
    """AC3: each row shows its own per-symbol score."""

    def test_multi_symbol_per_symbol_scores(self) -> None:
        reports = [
            _ms_make_report("a", score="LOW"),
            _ms_make_report("b", score="HIGH"),
            _ms_make_report("c", score="MEDIUM"),
        ]
        result = format_impact_compact(reports)
        rows = _ms_data_rows(result)
        assert "LOW" in rows[0]
        assert "HIGH" in rows[1]
        assert "MEDIUM" in rows[2]


class TestSingleSymbolViaMultiPath:
    """AC5: single-symbol via dict or list produces identical output."""

    def test_single_symbol_via_multi_path(self) -> None:
        report = _ms_make_report(
            "func_solo",
            module="pkg.solo",
            line=42,
            score="MEDIUM",
            callers=[_ms_caller("caller_a", "pkg.caller", 5)],
        )
        single_output = format_impact_compact(report)
        list_output = format_impact_compact([report])
        assert single_output == list_output


class TestProdTestSplitPerSymbol:
    """AC1+AC2: each row has correct Prod/Tests split."""

    def test_prod_test_split_per_symbol(self) -> None:
        reports = [
            _ms_make_report(
                "func_a",
                module="pkg.a",
                line=1,
                callers=[
                    _ms_caller("prod_call", "pkg.service", 10),
                    _ms_caller("test_call", "tests.test_a", 20),
                ],
            ),
            _ms_make_report(
                "func_b",
                module="pkg.b",
                line=2,
                callers=[
                    _ms_caller("other_prod", "pkg.other", 30),
                ],
            ),
        ]
        result = format_impact_compact(reports)
        rows = _ms_data_rows(result)

        assert "pkg.service:10" in rows[0]
        row0_has_test = "tests.test_a:20" in rows[0] or "test_a" in rows[0]
        assert row0_has_test

        assert "pkg.other:30" in rows[1]


class TestMultiSymbolEdgeCases:
    """Edge cases from the multi-symbol spec."""

    def test_symbol_with_no_callers(self) -> None:
        """One of 3 symbols has zero callers."""
        reports = [
            _ms_make_report(
                "func_a",
                callers=[_ms_caller("x", "pkg.x", 10)],
            ),
            _ms_make_report("func_empty"),  # no callers
            _ms_make_report(
                "func_c",
                callers=[_ms_caller("z", "pkg.z", 30)],
            ),
        ]
        result = format_impact_compact(reports)
        rows = _ms_data_rows(result)

        assert "—" in rows[1] or rows[1].count("|") >= 4

    def test_symbol_not_found(self) -> None:
        """Report has error, no definition."""
        reports = [
            _ms_make_report(
                "func_ok",
                callers=[_ms_caller("x", "pkg.x", 10)],
            ),
            _ms_make_report(
                "func_missing",
                error="symbol not resolved",
            ),
            _ms_make_report(
                "func_ok2",
                callers=[_ms_caller("z", "pkg.z", 30)],
            ),
        ]
        result = format_impact_compact(reports)
        rows = _ms_data_rows(result)

        assert "not found" in rows[1]
        assert "—" in rows[1]


# ── edge cases (bad path, etc.) ──


class TestImpactToolEdgeCasesUnit:
    """Cover tools/impact.py uncovered paths (no real I/O)."""

    def test_bad_path(self) -> None:
        result = ImpactTool().execute(path="/nonexistent/xyz", symbol="foo")
        assert result.success is False


# ── failure logging ──


@pytest.mark.integration
def test_impact_tool_logs_when_target_path_invalid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tool = ImpactTool()

    with caplog.at_level(logging.WARNING, logger="axm_ast.tools.impact"):
        result = tool.execute(path="/does/not/exist", symbol="foo")

    assert result.success is False

    records = [
        r
        for r in caplog.records
        if r.name == "axm_ast.tools.impact" and r.levelno == logging.WARNING
    ]
    assert records, "expected a WARNING record from axm_ast.tools.impact"
    assert any(r.exc_info is not None for r in records), (
        "expected exc_info to be populated on the warning record"
    )


# ── render ──


@pytest.fixture
def full_report() -> dict[str, Any]:
    """Report dict with all fields populated."""
    return {
        "symbol": "my_func",
        "score": "HIGH",
        "definition": {
            "kind": "function",
            "module": "pkg.mod",
            "line": 42,
            "signature": "def my_func(x: int) -> str",
        },
        "callers": [
            {"name": "caller_a", "module": "pkg.caller", "line": 10},
            {"name": "caller_b", "module": "pkg.other", "line": 20},
        ],
        "affected_modules": ["pkg.mod", "pkg.caller"],
        "test_files": ["tests/test_mod.py", "tests/sub/test_other.py"],
        "git_coupled": [
            {"file": "src/pkg/helper.py", "strength": 0.8, "co_changes": 4},
            {"file": "src/pkg/util.py", "strength": 0.6, "co_changes": 2},
        ],
        "cross_package_impact": [
            {"package": "other-pkg", "module": "other_pkg.api"},
            "plain_string_entry",
        ],
    }


@pytest.fixture
def minimal_report() -> dict[str, Any]:
    """Report dict with only symbol + score."""
    return {"symbol": "bare_sym", "score": "LOW"}


@pytest.fixture
def error_report() -> dict[str, Any]:
    """Report dict with an error key."""
    return {"symbol": "broken", "error": "could not resolve symbol"}


class TestRenderImpactSingleFull:
    """test_render_impact_single_full: all fields populated."""

    def test_header_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        lines = result.split("\n")
        assert lines[0] == "ast_impact | my_func | HIGH"

    def test_definition_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Def: pkg.mod:42 (function)" in result

    def test_signature_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "def my_func(x: int) -> str" in result

    def test_callers_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Callers: caller_a (pkg.caller:10), caller_b (pkg.other:20)" in result

    def test_affected_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Affected: pkg.mod, pkg.caller" in result

    def test_tests_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Tests: test_mod.py, test_other.py" in result

    def test_git_coupled_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Git-coupled: helper.py, util.py" in result

    def test_cross_package_line(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        assert "Cross-package: other-pkg, plain_string_entry" in result

    def test_full_output_matches(self, full_report: dict[str, Any]) -> None:
        result = _render_impact_single(full_report)
        expected = (
            "ast_impact | my_func | HIGH\n"
            "Def: pkg.mod:42 (function)\n"
            "def my_func(x: int) -> str\n"
            "Callers: caller_a (pkg.caller:10), caller_b (pkg.other:20)\n"
            "Affected: pkg.mod, pkg.caller\n"
            "Tests: test_mod.py, test_other.py\n"
            "Git-coupled: helper.py, util.py\n"
            "Cross-package: other-pkg, plain_string_entry"
        )
        assert result == expected


class TestRenderImpactSingleMinimal:
    """test_render_impact_single_minimal: only symbol + score."""

    def test_header_line(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        lines = result.split("\n")
        assert lines[0] == "ast_impact | bare_sym | LOW"

    def test_callers_none(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Callers: none" in result

    def test_tests_none(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Tests: none" in result

    def test_no_def_line(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Def:" not in result

    def test_no_affected(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Affected:" not in result

    def test_no_git_coupled(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Git-coupled:" not in result

    def test_no_cross_package(self, minimal_report: dict[str, Any]) -> None:
        result = _render_impact_single(minimal_report)
        assert "Cross-package:" not in result


class TestRenderImpactSingleError:
    """test_render_impact_single_error: report with error key."""

    def test_error_output(self, error_report: dict[str, Any]) -> None:
        result = _render_impact_single(error_report)
        assert result == "ast_impact | broken | error\ncould not resolve symbol"

    def test_error_no_extra_sections(self, error_report: dict[str, Any]) -> None:
        result = _render_impact_single(error_report)
        assert "Callers:" not in result
        assert "Tests:" not in result


class TestRenderImpactEdgeCases:
    def test_empty_callers_list(self) -> None:
        """Empty callers list -> 'Callers: none'."""
        report: dict[str, Any] = {"symbol": "s", "score": "LOW", "callers": []}
        result = _render_impact_single(report)
        assert "Callers: none" in result

    def test_cross_package_mixed_types(self) -> None:
        """Cross-package with both dict and str entries."""
        report: dict[str, Any] = {
            "symbol": "s",
            "score": "LOW",
            "cross_package_impact": [
                {"package": "pkg-a"},
                "raw-string",
                {"module": "fallback.mod"},
            ],
        }
        result = _render_impact_single(report)
        assert "Cross-package: pkg-a, raw-string, fallback.mod" in result

    def test_missing_definition(self) -> None:
        """No 'defn' key -> no 'Def:' line."""
        report: dict[str, Any] = {"symbol": "s", "score": "LOW"}
        result = _render_impact_single(report)
        assert "Def:" not in result

    def test_caller_without_line(self) -> None:
        """Caller entry missing line falls back to module only."""
        report: dict[str, Any] = {
            "symbol": "s",
            "score": "LOW",
            "callers": [{"name": "c", "module": "m"}],
        }
        result = _render_impact_single(report)
        assert "Callers: c (m)" in result


class TestRenderImpactText:
    def test_delegates_to_single(self, full_report: dict[str, Any]) -> None:
        assert render_impact_text(full_report) == _render_impact_single(full_report)

    def test_error_report(self, error_report: dict[str, Any]) -> None:
        assert render_impact_text(error_report) == _render_impact_single(error_report)


class TestRenderImpactBatchText:
    def test_empty_list(self) -> None:
        assert render_impact_batch_text([]) == ""

    def test_batch_header_max_score(
        self, full_report: dict[str, Any], minimal_report: dict[str, Any]
    ) -> None:
        result = render_impact_batch_text(
            cast("list[ImpactResult]", [full_report, minimal_report])
        )
        assert result.startswith("ast_impact | 2 symbols | max=HIGH")

    def test_batch_contains_all_symbols(
        self, full_report: dict[str, Any], minimal_report: dict[str, Any]
    ) -> None:
        result = render_impact_batch_text(
            cast("list[ImpactResult]", [full_report, minimal_report])
        )
        assert "## my_func | HIGH" in result
        assert "## bare_sym | LOW" in result


# ── severity ──


class TestFormatCompactUsesScoreNotSeverity:
    """AC3: format_impact_compact uses score only, no severity fallback."""

    def test_format_compact_uses_score_not_severity(self) -> None:
        impact = {
            "symbol": "bar",
            "score": "HIGH",
            "definition": {"file": "y.py", "line": 5},
            "callers": [],
            "test_files": [],
        }
        output = format_impact_compact(impact)
        assert "HIGH" in output

    def test_format_compact_dict_with_only_score(self) -> None:
        """Edge case: dict with score but no severity key."""
        impact = {
            "symbol": "baz",
            "score": "MEDIUM",
            "definition": {"file": "z.py", "line": 10},
            "callers": [],
            "test_files": [],
        }
        output = format_impact_compact(impact)
        assert "MEDIUM" in output
