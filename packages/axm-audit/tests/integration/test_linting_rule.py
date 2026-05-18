"""Integration tests for axm_audit.core.rules.quality (real fixture I/O).

Tests here consume the ``project_path`` fixture which performs ``mkdir`` /
``touch`` at setup; they belong to the integration tier even though the
in-body call to ``run_in_project`` is mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_audit.core.rules.quality import LintingRule
from axm_audit.models import CheckResult


@pytest.fixture()
def project_path(tmp_path: Path) -> Path:
    """Create a minimal project layout."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").touch()
    (tmp_path / "tests").mkdir()
    return tmp_path


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


def test_clean_project_high_score(tmp_path: Path) -> None:
    """Clean project should score 100."""

    # Create minimal clean Python file
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text('"""Package init."""\n')
    (src / "main.py").write_text(
        '"""Main module."""\n\n'
        "def hello() -> str:\n"
        '    """Return greeting."""\n'
        '    return "hello"\n'
    )

    rule = LintingRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert result.score == 100


def test_issues_reduce_score(tmp_path: Path) -> None:
    """Lint issues should reduce score."""

    src = tmp_path / "src"
    src.mkdir()
    # Create file with lint issues (unused import)
    (src / "bad.py").write_text("import os\nimport sys\n")

    rule = LintingRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert result.score is not None
    assert result.score < 100
    assert result.details["issue_count"] > 0


def test_lint_details_has_issues_key(tmp_path: Path) -> None:
    """details must contain an 'issues' key with a list."""

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text('"""Package init."""\n')

    rule = LintingRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    assert "issues" in result.details
    assert isinstance(result.details["issues"], list)


def test_lint_issues_match_count(tmp_path: Path) -> None:
    """len(details['issues']) must equal issue_count (up to cap of 20)."""

    src = tmp_path / "src"
    src.mkdir()
    (src / "bad.py").write_text("import os\nimport sys\n")

    rule = LintingRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    expected = min(result.details["issue_count"], 20)
    assert len(result.details["issues"]) == expected


def test_lint_threshold_unchanged(tmp_path: Path) -> None:
    """Lint rule still uses score threshold — no regression from type fix."""

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text('"""Package."""\n')
    # Single unused import → small score reduction, still above threshold
    (src / "mild.py").write_text('"""Mild issue."""\nimport os\n')

    rule = LintingRule()
    result = rule.check(tmp_path)
    assert result.details is not None
    # Lint uses scoring threshold, not zero-tolerance
    assert result.details["issue_count"] > 0
    assert result.score is not None
    assert result.score >= 90


def test_linting_uses_run_in_project(tmp_path: Path) -> None:
    """LintingRule should call run_in_project."""

    (tmp_path / "src").mkdir()

    with patch("axm_audit.core.rules.quality.run_in_project") as mock:
        mock.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
        LintingRule().check(tmp_path)
        mock.assert_called_once()
        assert mock.call_args[0][0][0] == "ruff"


def test_linting_injects_ruff(tmp_path: Path) -> None:
    """LintingRule passes with_packages=["ruff"]."""

    (tmp_path / "src").mkdir()

    with patch("axm_audit.core.rules.quality.run_in_project") as mock:
        mock.return_value = MagicMock(stdout="[]", stderr="", returncode=0)
        LintingRule().check(tmp_path)
        assert mock.call_args[1]["with_packages"] == ["ruff"]


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
