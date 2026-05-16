"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.core.checker import format_report
from axm_init.models.check import CheckResult, ProjectResult


class TestFormatReportContext:
    """Format report shows context in header."""

    def test_format_report_context(self, tmp_path: Path) -> None:
        """Report header contains context info."""
        checks = [
            CheckResult(
                name="t.check",
                category="t",
                passed=True,
                weight=10,
                message="ok",
                details=[],
                fix="",
            )
        ]
        result = ProjectResult.from_checks(
            tmp_path, checks, context="workspace", workspace_root=tmp_path
        )
        report = format_report(result)
        assert "Context: WORKSPACE" in report
