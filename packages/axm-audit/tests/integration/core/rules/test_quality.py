"""Integration tests for axm_audit.core.rules.quality (real fixture I/O).

Tests here consume the ``project_path`` fixture which performs ``mkdir`` /
``touch`` at setup; they belong to the integration tier even though the
in-body call to ``run_in_project`` is mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality import LintingRule


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
