"""Unit tests targeting coverage gaps — AXM-982 (no real I/O)."""

from __future__ import annotations


class TestImpactToolEdgeCasesUnit:
    """Cover tools/impact.py uncovered paths (no real I/O)."""

    def test_bad_path(self) -> None:
        from axm_ast.tools.impact import ImpactTool

        result = ImpactTool().execute(path="/nonexistent/xyz", symbol="foo")
        assert result.success is False
