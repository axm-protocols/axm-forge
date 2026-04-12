from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture()
def impact_tool():
    from axm_ast.tools.impact import ImpactTool

    return ImpactTool.__new__(ImpactTool)


class TestAnalyzeSingleNoSeverityKey:
    """AC1: _analyze_single no longer sets impact['severity']."""

    def test_analyze_single_no_severity_key(self, impact_tool, tmp_path):
        fake_impact = {
            "symbol": "foo",
            "score": "HIGH",
            "definition": {"file": "x.py", "line": 1},
            "callers": [],
            "test_files": [],
        }
        with patch(
            "axm_ast.core.impact.analyze_impact_workspace",
            return_value=fake_impact,
        ):
            result = impact_tool._analyze_single(tmp_path, "foo")

        assert "severity" not in result
        assert result["score"] == "HIGH"


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
