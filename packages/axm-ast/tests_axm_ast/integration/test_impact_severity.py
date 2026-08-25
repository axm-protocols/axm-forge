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
