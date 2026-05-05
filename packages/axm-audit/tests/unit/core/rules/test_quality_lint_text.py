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


class TestLintTextNoIndent:
    def test_lines_start_with_bullet(self, lint_result):
        """text lines start with • (no leading spaces)."""
        for line in lint_result.text.splitlines():
            assert line.startswith("•"), f"Line has leading spaces: {line!r}"


class TestLintTextNoBrackets:
    def test_no_brackets_around_code(self, lint_result):
        """No [ or ] around ruff code in text."""
        assert "[" not in lint_result.text
        assert "]" not in lint_result.text


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
        """details keys are issue_count, checked, issues; score is on the model."""
        assert set(lint_result.details.keys()) == {
            "issue_count",
            "checked",
            "issues",
        }
        assert lint_result.score is not None

    def test_issues_file_absolute(self, lint_result, project_path):
        """issues[].file still uses absolute paths."""
        for issue in lint_result.details["issues"]:
            assert issue["file"].startswith(str(project_path))
