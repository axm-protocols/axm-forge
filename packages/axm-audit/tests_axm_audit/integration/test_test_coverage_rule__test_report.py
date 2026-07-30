"""Split from ``test_subprocess_runner_layouts.py``."""

from pathlib import Path
from unittest.mock import patch


def test_coverage_uses_run_tests(tmp_path: Path) -> None:
    """TestCoverageRule should delegate to run_tests."""
    from axm_audit.core.rules.coverage import TestCoverageRule
    from axm_audit.core.test_runner import TestReport

    mock_report = TestReport(passed=42, failed=0, duration=5.0, coverage=95.0)
    with patch(
        "axm_audit.core.test_runner.run_tests", return_value=mock_report
    ) as mock:
        TestCoverageRule().check(tmp_path)
        mock.assert_called_once()
