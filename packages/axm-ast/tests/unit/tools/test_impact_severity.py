from __future__ import annotations


class TestFormatCompactUsesScoreNotSeverity:
    """AC3: format_impact_compact uses score only, no severity fallback."""

    def test_format_compact_uses_score_not_severity(self):
        from axm_ast.tools.impact import format_impact_compact

        impact = {
            "symbol": "bar",
            "score": "HIGH",
            "definition": {"file": "y.py", "line": 5},
            "callers": [],
            "test_files": [],
        }
        output = format_impact_compact(impact)
        assert "HIGH" in output

    def test_format_compact_dict_with_only_score(self):
        """Edge case: dict with score but no severity key."""
        from axm_ast.tools.impact import format_impact_compact

        impact = {
            "symbol": "baz",
            "score": "MEDIUM",
            "definition": {"file": "z.py", "line": 10},
            "callers": [],
            "test_files": [],
        }
        output = format_impact_compact(impact)
        assert "MEDIUM" in output
