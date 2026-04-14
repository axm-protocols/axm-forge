from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality import LintingRule
from axm_audit.models import CheckResult


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


# ---------- Unit tests ----------


class TestLintTextNoIndent:
    def test_lines_start_with_bullet(self, lint_result):
        """text lines start with \u2022 (no leading spaces)."""
        for line in lint_result.text.splitlines():
            assert line.startswith("\u2022"), f"Line has leading spaces: {line!r}"


class TestLintTextNoBrackets:
    def test_no_brackets_around_code(self, lint_result):
        """No [ or ] around ruff code in text."""
        assert "[" not in lint_result.text
        assert "]" not in lint_result.text


class TestLintTextRelativePaths:
    def test_paths_are_relative(self, lint_result, project_path):
        """Paths in text are relative (no project_path prefix)."""
        abs_prefix = str(project_path)
        for line in lint_result.text.splitlines():
            assert abs_prefix not in line, f"Absolute path found: {line!r}"
        # Should contain relative path
        assert "src/mod.py" in lint_result.text


class TestLintTextNoneWhenPassed:
    def test_text_is_none(self, project_path, monkeypatch):
        """text is None when project is clean."""
        mock_run = MagicMock()
        mock_run.return_value.stdout = "[]"
        monkeypatch.setattr("axm_audit.core.rules.quality.run_in_project", mock_run)
        rule = LintingRule()
        result = rule.check(project_path)
        assert result.text is None


class TestDetailsUnchanged:
    def test_details_keys(self, lint_result):
        """details keys are issue_count, score, checked, issues."""
        assert set(lint_result.details.keys()) == {
            "issue_count",
            "score",
            "checked",
            "issues",
        }

    def test_issues_file_absolute(self, lint_result, project_path):
        """issues[].file still uses absolute paths."""
        for issue in lint_result.details["issues"]:
            assert issue["file"].startswith(str(project_path))


# ---------- Functional tests ----------


class TestFormatReportIndentation:
    def test_detail_lines_indented(self, lint_result):
        """Report output has indented detail lines (5-space prefix)."""
        from axm_audit.formatters import _format_check_details

        detail_lines = _format_check_details(lint_result)
        for line in detail_lines:
            assert line.startswith("     "), f"Missing 5-space indent: {line!r}"


class TestFormatReportAlignmentUnchanged:
    def test_visual_structure(self, lint_result):
        """Failures section maintains visual alignment."""
        from axm_audit.formatters import _format_failures
        from axm_audit.models import AuditResult

        audit = AuditResult(checks=[lint_result])
        lines = _format_failures(audit)
        # Should have failure header, rule_id, problem, detail lines, fix hint
        assert any("\u274c" in line for line in lines)
        assert any("Problem:" in line for line in lines)
        # Detail lines (bullets) should be indented
        bullet_lines = [ln for ln in lines if "\u2022" in ln]
        for bl in bullet_lines:
            assert bl.startswith("     "), f"Bullet not indented: {bl!r}"


# ---------- Edge cases ----------


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
        """_format_check_details adds indent to any rule's text."""
        from axm_audit.formatters import _format_check_details
        from axm_audit.models import CheckResult, Severity

        check = CheckResult(
            rule_id="OTHER_RULE",
            passed=False,
            message="Some issue",
            severity=Severity.WARNING,
            details={},
            text="line one\nline two",
        )
        lines = _format_check_details(check)
        for line in lines:
            assert line.startswith("     "), f"Missing indent: {line!r}"
