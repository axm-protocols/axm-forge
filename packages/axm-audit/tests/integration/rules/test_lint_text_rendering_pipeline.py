from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality import LintingRule
from axm_audit.models import CheckResult

pytestmark = pytest.mark.integration


def _make_ruff_output(project_path: Path, count: int = 3) -> str:
    """Build fake ruff JSON output with *count* issues."""
    issues = [
        {
            "filename": str(project_path / "src" / "mod.py"),
            "location": {"row": 10 + i},
            "code": f"E50{i}",
            "message": f"Issue number {i}",
        }
        for i in range(count)
    ]
    return json.dumps(issues)


@pytest.fixture()
def project_path(tmp_path: Path) -> Path:
    """Create a minimal project layout."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").touch()
    (tmp_path / "tests").mkdir()
    return tmp_path


@pytest.fixture()
def lint_result(project_path: Path, monkeypatch: pytest.MonkeyPatch) -> CheckResult:
    """Run LintingRule.check with mocked ruff returning 3 issues."""
    mock_run = MagicMock()
    mock_run.return_value.stdout = _make_ruff_output(project_path, count=3)
    monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
    rule = LintingRule()
    return rule.check(project_path)


class TestLintTextRelativePaths:
    def test_paths_are_relative(self, lint_result, project_path):
        """Paths in text are relative (no project_path prefix)."""
        abs_prefix = str(project_path)
        for line in lint_result.text.splitlines():
            assert abs_prefix not in line, f"Absolute path found: {line!r}"
        assert "src/mod.py" in lint_result.text


class TestFormatReportIndentation:
    def test_detail_lines_indented(self, lint_result):
        """Report output has indented detail lines (5-space prefix)."""
        from axm_audit.formatters import format_report
        from axm_audit.models import AuditResult

        report = format_report(AuditResult(checks=[lint_result]))
        bullet_lines = [ln for ln in report.splitlines() if "•" in ln]
        assert bullet_lines, "expected at least one bullet detail line"
        for line in bullet_lines:
            assert line.startswith("     "), f"Missing 5-space indent: {line!r}"


class TestFormatReportAlignmentUnchanged:
    def test_visual_structure(self, lint_result):
        """Failures section maintains visual alignment."""
        from axm_audit.formatters import format_report
        from axm_audit.models import AuditResult

        report = format_report(AuditResult(checks=[lint_result]))
        lines = report.splitlines()
        assert any("❌" in line for line in lines)
        assert any("Problem:" in line for line in lines)
        bullet_lines = [ln for ln in lines if "•" in ln]
        for bl in bullet_lines:
            assert bl.startswith("     "), f"Bullet not indented: {bl!r}"


class TestPathOutsideProject:
    def test_short_path_fallback(self, project_path, monkeypatch):
        """File outside project_path keeps original path."""
        issues = [
            {
                "filename": "/other/place/file.py",
                "location": {"row": 1},
                "code": "E501",
                "message": "Line too long",
            }
        ]
        mock_run = MagicMock()
        mock_run.return_value.stdout = json.dumps(issues)
        monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
        rule = LintingRule()
        result = rule.check(project_path)
        assert result.text is not None
        assert "/other/place/file.py" in result.text


class TestZeroIssuesPassed:
    def test_no_crash_text_none(self, project_path, monkeypatch):
        """Clean project: text=None, no crash."""
        mock_run = MagicMock()
        mock_run.return_value.stdout = "[]"
        monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
        rule = LintingRule()
        result = rule.check(project_path)
        assert result.text is None
        assert result.passed is True


class TestTwentyIssuesCap:
    def test_capped_at_twenty(self, project_path, monkeypatch):
        """text has exactly 20 lines, details.issues has 20 entries."""
        issues = [
            {
                "filename": str(project_path / "src" / "mod.py"),
                "location": {"row": i},
                "code": "E501",
                "message": f"Issue {i}",
            }
            for i in range(25)
        ]
        mock_run = MagicMock()
        mock_run.return_value.stdout = json.dumps(issues)
        monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
        rule = LintingRule()
        result = rule.check(project_path)
        assert result.text is not None
        assert result.details is not None
        assert len(result.text.splitlines()) == 20
        assert len(result.details["issues"]) == 20


class TestOtherRulesTextRendering:
    def test_format_check_details_adds_indent(self):
        """Rendered failure details from check.text are 5-space indented."""
        from axm_audit.formatters import format_report
        from axm_audit.models import AuditResult, CheckResult, Severity

        check = CheckResult(
            rule_id="OTHER_RULE",
            passed=False,
            message="Some issue",
            severity=Severity.WARNING,
            details={},
            text="line one\nline two",
        )
        report = format_report(AuditResult(checks=[check]))
        assert "     line one" in report
        assert "     line two" in report
