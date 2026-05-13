"""TDD tests for compact output mode on ast_impact (AXM-940).

Tests cover:
- Unit: format_impact_compact formatter
- Functional: ImpactTool.execute(detail="compact"), ImpactHook with detail param
- Edge cases: not found, no tests, workspace mode
"""

from __future__ import annotations

from typing import Any

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_impact_dict(
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


# ─── Unit: format_impact_compact ─────────────────────────────────────────────


class TestFormatImpactCompactSingle:
    """Single-symbol compact formatting."""

    def test_format_impact_compact_single(self) -> None:
        """1 definition + 3 callers → table row + caller summary."""
        from axm_ast.tools.impact import format_impact_compact

        impact = _make_impact_dict(
            symbol="greet",
            callers=[
                {"name": "main", "module": "demo.cli", "line": 10},
                {"name": "run", "module": "demo.app", "line": 20},
                {"name": "test_greet", "module": "tests.test_core"},
            ],
        )
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        # Table headers
        assert "Symbol" in result
        assert "Score" in result
        # Symbol row with definition location
        assert "greet" in result
        assert "demo.core:10" in result
        assert "MEDIUM" in result
        # New table format: separate Prod / Direct tests / Indirect tests columns
        assert "Prod" in result
        assert "demo.cli:10" in result
        assert "demo.app:20" in result
        assert "test_core" in result


class TestFormatImpactCompactMulti:
    """Multi-symbol (merged) compact formatting."""

    def test_format_impact_compact_multi(self) -> None:
        """List of 4 reports → table with 4 per-symbol rows."""
        from axm_ast.tools.impact import format_impact_compact

        reports = [
            _make_impact_dict(
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
        # Should have rows for all definitions
        assert "mod_a" in result
        assert "mod_b" in result
        assert "mod_c" in result
        assert "mod_d" in result
        assert "MEDIUM" in result


class TestFormatImpactCompactNoCallers:
    """Compact formatting when no callers exist."""

    def test_format_impact_compact_no_callers(self) -> None:
        """Symbol with 0 callers → table shows em-dash for callers."""
        from axm_ast.tools.impact import format_impact_compact

        impact = _make_impact_dict(symbol="lonely", callers=[], score="LOW")
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "\u2014" in result  # em-dash = no callers
        assert "lonely" in result


class TestFormatImpactCompactTestExposure:
    """Compact formatting with test file exposure."""

    def test_format_impact_compact_test_exposure(self) -> None:
        """Dict with test_files → footer lists file names."""
        from axm_ast.tools.impact import format_impact_compact

        impact = _make_impact_dict(
            test_files=["test_core.py", "test_cli.py", "test_integration.py"],
        )
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "test_core.py" in result
        assert "test_cli.py" in result
        assert "test_integration.py" in result


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestImpactCompactEdgeCases:
    """Edge cases for compact output mode."""

    def test_symbol_not_found(self) -> None:
        """Unknown symbol → row with 'not found' indicator."""
        from axm_ast.tools.impact import format_impact_compact

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
        from axm_ast.tools.impact import format_impact_compact

        impact = _make_impact_dict(test_files=[])
        result = format_impact_compact(impact)
        assert isinstance(result, str)
        assert "no test coverage" in result
