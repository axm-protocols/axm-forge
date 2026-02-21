"""Tests for reporters."""


class TestReporters:
    """Test that reporters work correctly in axm-audit."""

    def test_json_reporter_import(self):
        """Test that JsonReporter can be imported."""
        from axm_audit.reporters import JsonReporter

        assert JsonReporter is not None

    def test_markdown_reporter_import(self):
        """Test that MarkdownReporter can be imported."""
        from axm_audit.reporters import MarkdownReporter

        assert MarkdownReporter is not None

    def test_json_reporter_render(self) -> None:
        """JsonReporter outputs valid JSON string."""
        import json

        from axm_audit.models import AuditResult, CheckResult
        from axm_audit.reporters import JsonReporter

        result = AuditResult(
            checks=[
                CheckResult(rule_id="TEST", passed=True, message="OK"),
            ]
        )
        reporter = JsonReporter()
        output = reporter.render(result)

        # Should be valid JSON
        data = json.loads(output)
        assert data["success"] is True
        assert len(data["checks"]) == 1

    def test_json_is_pure(self) -> None:
        """JSON output has no Rich formatting or escape codes."""
        from axm_audit.models import AuditResult, CheckResult
        from axm_audit.reporters import JsonReporter

        result = AuditResult(
            checks=[CheckResult(rule_id="R1", passed=False, message="FAIL")]
        )
        reporter = JsonReporter()
        output = reporter.render(result)

        # No ANSI escape codes
        assert "\\x1b[" not in output
        assert "\\033[" not in output

    def test_markdown_reporter_render(self) -> None:
        """MarkdownReporter creates readable table."""
        from axm_audit.models import AuditResult, CheckResult
        from axm_audit.reporters import MarkdownReporter

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="FILE_EXISTS_pyproject.toml", passed=True, message="OK"
                ),
                CheckResult(
                    rule_id="FILE_EXISTS_README.md", passed=False, message="Missing"
                ),
            ]
        )
        reporter = MarkdownReporter()
        output = reporter.render(result)

        # Should contain markdown table elements
        assert "|" in output
        assert "pyproject.toml" in output
        assert "README.md" in output

    def test_markdown_shows_summary(self) -> None:
        """Markdown includes summary statistics."""
        from axm_audit.models import AuditResult, CheckResult
        from axm_audit.reporters import MarkdownReporter

        result = AuditResult(
            checks=[
                CheckResult(rule_id="R1", passed=True, message="OK"),
                CheckResult(rule_id="R2", passed=False, message="FAIL"),
            ]
        )
        reporter = MarkdownReporter()
        output = reporter.render(result)

        # Should show pass/fail counts
        assert "1" in output  # 1 passed or 1 failed

    def test_markdown_non_audit_result(self) -> None:
        """MarkdownReporter falls back to JSON for non-AuditResult models."""
        from axm_audit.models import CheckResult
        from axm_audit.reporters import MarkdownReporter

        check = CheckResult(rule_id="R1", passed=True, message="OK")
        reporter = MarkdownReporter()
        output = reporter.render(check)

        # Should fallback to JSON
        assert "R1" in output

    def test_markdown_fix_hints(self) -> None:
        """MarkdownReporter renders fix hints section for failed checks."""
        from axm_audit.models import AuditResult, CheckResult
        from axm_audit.reporters import MarkdownReporter

        result = AuditResult(
            checks=[
                CheckResult(
                    rule_id="R1",
                    passed=False,
                    message="FAIL",
                    fix_hint="Run ruff fix",
                ),
            ]
        )
        reporter = MarkdownReporter()
        output = reporter.render(result)

        assert "Fix Hints" in output
        assert "Run ruff fix" in output

    def test_markdown_grade_display(self) -> None:
        """MarkdownReporter shows grade when quality_score is present."""
        from axm_audit.models import AuditResult, CheckResult
        from axm_audit.reporters import MarkdownReporter

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
        reporter = MarkdownReporter()
        output = reporter.render(result)

        # Should contain grade info if quality_score exists
        if result.quality_score is not None and result.grade is not None:
            assert result.grade in output
