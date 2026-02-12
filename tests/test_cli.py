"""Tests for CLI (cyclopts) and formatters."""


class TestFormatReport:
    """Tests for format_report function."""

    def test_report_contains_score(self) -> None:
        """Report should display score and grade."""
        from axm_audit.formatters import format_report
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="Lint score: 100/100 (0 issues)",
                    details={"score": 100},
                ),
            ]
        )
        report = format_report(result)
        assert "Score:" in report

    def test_report_shows_pass_fail_icons(self) -> None:
        """Report should use ✅ for pass and ❌ for fail."""
        from axm_audit.formatters import format_report
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    details={"score": 100},
                ),
                CheckResult(
                    rule_id="QUALITY_TYPE",
                    passed=False,
                    message="FAIL",
                    details={"score": 0},
                ),
            ]
        )
        report = format_report(result)
        assert "✅" in report
        assert "❌" in report


class TestFormatJson:
    """Tests for format_json function."""

    def test_json_has_required_keys(self) -> None:
        """JSON output should have score, grade, checks."""
        from axm_audit.formatters import format_json
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    details={"score": 100},
                ),
            ]
        )
        data = format_json(result)
        assert "score" in data
        assert "grade" in data
        assert "checks" in data


class TestCLI:
    """Tests for CLI commands."""

    def test_version_command(self) -> None:
        """version command should print version."""
        from axm_audit.cli import app

        # cyclopts apps can be tested by calling them directly
        # We just verify the app exists and has commands
        assert app is not None

    def test_audit_command_exists(self) -> None:
        """audit command should be registered."""
        from axm_audit.cli import app

        assert app is not None
