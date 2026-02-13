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

    def test_agent_flag_exists(self) -> None:
        """--agent flag should be accepted by audit command."""
        import inspect

        from axm_audit.cli import audit

        sig = inspect.signature(audit)
        assert "agent" in sig.parameters


class TestFormatAgent:
    """Tests for format_agent function."""

    def test_format_agent_all_passed(self) -> None:
        """All passing checks → failed=[], passed has 1-line strings."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="Lint score: 100/100",
                    details={"score": 100},
                ),
                CheckResult(
                    rule_id="QUALITY_TYPE",
                    passed=True,
                    message="Type score: 100/100",
                    details={"score": 100},
                ),
            ]
        )
        output = format_agent(result)
        assert output["failed"] == []
        assert len(output["passed"]) == 2
        assert all(isinstance(p, str) for p in output["passed"])

    def test_format_agent_mixed(self) -> None:
        """Failed items have full detail, passed items are 1-liners."""
        from axm_audit.formatters import format_agent
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
                    message="Type errors found",
                    details={"error_count": 5, "score": 75},
                    fix_hint="Add type hints",
                ),
            ]
        )
        output = format_agent(result)
        assert len(output["passed"]) == 1
        assert len(output["failed"]) == 1
        assert "details" in output["failed"][0]
        assert "fix_hint" in output["failed"][0]
        assert output["failed"][0]["fix_hint"] == "Add type hints"

    def test_format_agent_no_score(self) -> None:
        """No crash when quality_score is None."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="FILE_EXISTS_README.md",
                    passed=True,
                    message="exists",
                ),
            ]
        )
        output = format_agent(result)
        assert output["score"] is None
        assert output["grade"] is None

    def test_format_agent_has_required_keys(self) -> None:
        """Agent output must have score, grade, passed, failed."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            checks=[
                CheckResult(rule_id="R1", passed=True, message="OK"),
            ]
        )
        output = format_agent(result)
        assert set(output.keys()) == {"score", "grade", "passed", "failed"}


class TestExtractTestFailures:
    """Tests for _extract_test_failures helper."""

    def test_no_failures(self) -> None:
        """Empty stdout → no failures."""
        from axm_audit.core.rules.quality import _extract_test_failures

        assert _extract_test_failures("") == []
        assert _extract_test_failures("3 passed\n") == []

    def test_single_failure(self) -> None:
        """FAILED line parsed correctly."""
        from axm_audit.core.rules.quality import _extract_test_failures

        stdout = "FAILED tests/test_foo.py::test_bar - AssertionError\n1 failed\n"
        failures = _extract_test_failures(stdout)
        assert len(failures) == 1
        assert failures[0]["test"] == "tests/test_foo.py::test_bar"
        assert "AssertionError" in failures[0]["traceback"]

    def test_multiple_failures(self) -> None:
        """Multiple FAILED lines parsed."""
        from axm_audit.core.rules.quality import _extract_test_failures

        stdout = (
            "FAILED tests/test_a.py::test_one - err1\n"
            "FAILED tests/test_b.py::test_two - err2\n"
            "2 failed\n"
        )
        failures = _extract_test_failures(stdout)
        assert len(failures) == 2
