"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.core.checker import format_report
from tests.integration._helpers import _make_result


class TestFormatReport:
    """Tests for format_report()."""

    def test_contains_score_and_grade(self, tmp_path: Path) -> None:
        result = _make_result(tmp_path, passed=True)
        report = format_report(result)
        assert "100" in report
        assert "A" in report


class TestFormatReportVerbose:
    """Tests for format_report() verbose flag."""

    def test_default_hides_individual_passed(self, tmp_path: Path) -> None:
        """Default output shows summary line, not individual check names."""
        result = _make_result(tmp_path, passed=True)
        report = format_report(result)
        assert "1 checks passed" in report
        assert "test.check" not in report

    def test_verbose_shows_individual_checks(self, tmp_path: Path) -> None:
        """Verbose output shows individual check names."""
        result = _make_result(tmp_path, passed=True)
        report = format_report(result, verbose=True)
        assert "test.check" in report
        assert "✅" in report

    def test_default_always_shows_failures(self, tmp_path: Path) -> None:
        """Failures are always shown in default mode (failure icon + fix hint)."""
        result = _make_result(tmp_path, passed=False)
        report = format_report(result)
        assert "❌" in report
        assert "Run fix command" in report
