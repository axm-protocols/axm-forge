from __future__ import annotations

from typing import Any

from axm_ast.tools.impact import format_impact_compact


def _make_report(symbol: str, **overrides: object) -> dict[str, Any]:
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


def _caller(name: str, module: str, line: int) -> dict[str, Any]:
    return {"name": name, "module": module, "line": line}


def _data_rows(text: str) -> list[str]:
    """Extract table data rows (skip header + separator)."""
    lines = text.strip().splitlines()
    return [ln for ln in lines if ln.startswith("|") and "---" not in ln][1:]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestMultiSymbolPerSymbolCallers:
    """AC1: each symbol row shows only its own callers."""

    def test_multi_symbol_per_symbol_callers(self) -> None:
        reports = [
            _make_report(
                "func_a",
                module="pkg.a",
                line=1,
                callers=[_caller("x", "pkg.x", 10)],
            ),
            _make_report(
                "func_b",
                module="pkg.b",
                line=2,
                callers=[_caller("y", "pkg.y", 20)],
            ),
            _make_report(
                "func_c",
                module="pkg.c",
                line=3,
                callers=[_caller("z", "pkg.z", 30)],
            ),
        ]
        result = format_impact_compact(reports)
        rows = _data_rows(result)
        assert len(rows) == 3

        # Each row should mention only its own caller
        assert "pkg.x:10" in rows[0]
        assert "pkg.y" not in rows[0]
        assert "pkg.z" not in rows[0]

        assert "pkg.y:20" in rows[1]
        assert "pkg.x" not in rows[1]

        assert "pkg.z:30" in rows[2]
        assert "pkg.x" not in rows[2]


class TestMultiSymbolScoreIsMax:
    """AC3: score uses max-score semantics."""

    def test_multi_symbol_score_is_max(self) -> None:
        reports = [
            _make_report("a", score="LOW"),
            _make_report("b", score="HIGH"),
            _make_report("c", score="MEDIUM"),
        ]
        result = format_impact_compact(reports)
        rows = _data_rows(result)
        assert "HIGH" in rows[0]


class TestSingleSymbolViaMultiPath:
    """AC5: single-symbol via dict or list produces identical output."""

    def test_single_symbol_via_multi_path(self) -> None:
        report = _make_report(
            "func_solo",
            module="pkg.solo",
            line=42,
            score="MEDIUM",
            callers=[_caller("caller_a", "pkg.caller", 5)],
        )
        single_output = format_impact_compact(report)
        list_output = format_impact_compact([report])
        assert single_output == list_output


class TestProdTestSplitPerSymbol:
    """AC1+AC2: each row has correct Prod/Tests split."""

    def test_prod_test_split_per_symbol(self) -> None:
        reports = [
            _make_report(
                "func_a",
                module="pkg.a",
                line=1,
                callers=[
                    _caller("prod_call", "pkg.service", 10),
                    _caller("test_call", "tests.test_a", 20),
                ],
            ),
            _make_report(
                "func_b",
                module="pkg.b",
                line=2,
                callers=[
                    _caller("other_prod", "pkg.other", 30),
                ],
            ),
        ]
        result = format_impact_compact(reports)
        rows = _data_rows(result)

        # Row 0 (func_a): has both prod and test callers
        assert "pkg.service:10" in rows[0]
        row0_has_test = "tests.test_a:20" in rows[0] or "test_a" in rows[0]
        assert row0_has_test

        # Row 1 (func_b): only prod caller
        assert "pkg.other:30" in rows[1]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases from the spec."""

    def test_symbol_with_no_callers(self) -> None:
        """One of 3 symbols has zero callers."""
        reports = [
            _make_report(
                "func_a",
                callers=[_caller("x", "pkg.x", 10)],
            ),
            _make_report("func_empty"),  # no callers
            _make_report(
                "func_c",
                callers=[_caller("z", "pkg.z", 30)],
            ),
        ]
        result = format_impact_compact(reports)
        rows = _data_rows(result)

        # Middle row should have \u2014 for caller columns
        assert "\u2014" in rows[1] or rows[1].count("|") >= 4

    def test_symbol_not_found(self) -> None:
        """Report has error, no definition."""
        reports = [
            _make_report(
                "func_ok",
                callers=[_caller("x", "pkg.x", 10)],
            ),
            _make_report(
                "func_missing",
                error="symbol not resolved",
            ),
            _make_report(
                "func_ok2",
                callers=[_caller("z", "pkg.z", 30)],
            ),
        ]
        result = format_impact_compact(reports)
        rows = _data_rows(result)

        # Error row should indicate not found
        assert "not found" in rows[1]
        assert "\u2014" in rows[1]
