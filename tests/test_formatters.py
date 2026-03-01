"""Tests for formatters — format_report(), format_json(), format_agent()."""

from __future__ import annotations


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

    def test_format_report_shows_project_path(self) -> None:
        """Report header should display the actual project path."""
        from axm_audit.formatters import format_report
        from axm_audit.models.results import AuditResult, CheckResult

        result = AuditResult(
            project_path="/tmp/my-project",
            checks=[
                CheckResult(
                    rule_id="QUALITY_LINT",
                    passed=True,
                    message="OK",
                    details={"score": 100},
                ),
            ],
        )
        report = format_report(result)
        assert "/tmp/my-project" in report

    def test_format_report_no_checks(self) -> None:
        """Empty checks list should not crash, still shows path."""
        from axm_audit.formatters import format_report
        from axm_audit.models.results import AuditResult

        result = AuditResult(project_path="/tmp/p", checks=[])
        report = format_report(result)
        assert "/tmp/p" in report

    def test_format_report_no_path_fallback(self) -> None:
        """Missing project_path falls back to 'unknown'."""
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
            ],
        )
        report = format_report(result)
        assert "unknown" in report


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
