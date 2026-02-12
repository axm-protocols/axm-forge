"""Tests for SecurityRule (Bandit integration)."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from axm_audit.core.rules.security import SecurityRule
from axm_audit.models.results import Severity


class TestSecurityRule:
    """Tests for SecurityRule (Bandit integration)."""

    def test_rule_id(self):
        """Rule ID should be QUALITY_SECURITY."""
        rule = SecurityRule()
        assert rule.rule_id == "QUALITY_SECURITY"

    def test_no_src_directory(self, tmp_path: Path):
        """Should return error if src/ doesn't exist."""
        rule = SecurityRule()
        result = rule.check(tmp_path)

        assert not result.passed
        assert result.severity == Severity.ERROR
        assert "src/ directory not found" in result.message

    def test_no_issues_perfect_score(self, tmp_path: Path, monkeypatch):
        """Should return 100/100 if no security issues."""
        src_path = tmp_path / "src"
        src_path.mkdir()

        # Mock subprocess.run to return no issues
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "results": [],
                "metrics": {
                    "_totals": {
                        "SEVERITY.HIGH": 0,
                        "SEVERITY.MEDIUM": 0,
                        "SEVERITY.LOW": 0,
                    }
                },
            }
        )
        mock_result.returncode = 0

        mock_run = MagicMock(return_value=mock_result)
        monkeypatch.setattr(subprocess, "run", mock_run)

        rule = SecurityRule()
        result = rule.check(tmp_path)

        assert result.passed
        assert result.details["score"] == 100
        assert result.details["high_count"] == 0
        assert result.details["medium_count"] == 0
        assert result.severity == Severity.INFO

    def test_high_severity_issues_scoring(self, tmp_path: Path, monkeypatch):
        """Should penalize high severity issues heavily (15 points each)."""
        src_path = tmp_path / "src"
        src_path.mkdir()

        # Mock 2 HIGH, 1 MEDIUM issue
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "results": [
                    {"issue_severity": "HIGH", "issue_text": "Use of exec()"},
                    {"issue_severity": "HIGH", "issue_text": "Hardcoded password"},
                    {"issue_severity": "MEDIUM", "issue_text": "Weak crypto"},
                ],
                "metrics": {
                    "_totals": {
                        "SEVERITY.HIGH": 2,
                        "SEVERITY.MEDIUM": 1,
                        "SEVERITY.LOW": 0,
                    }
                },
            }
        )

        mock_run = MagicMock(return_value=mock_result)
        monkeypatch.setattr(subprocess, "run", mock_run)

        rule = SecurityRule()
        result = rule.check(tmp_path)

        # Score = 100 - (2*15 + 1*5) = 100 - 35 = 65
        assert result.details["score"] == 65
        assert result.details["high_count"] == 2
        assert result.details["medium_count"] == 1
        assert not result.passed  # < 80
        assert result.severity == Severity.WARNING

    def test_top_issues_reported(self, tmp_path: Path, monkeypatch):
        """Should report top 5 security issues."""
        src_path = tmp_path / "src"
        src_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "results": [
                    {
                        "issue_severity": "HIGH",
                        "issue_text": "Use of exec()",
                        "filename": "src/main.py",
                        "line_number": 42,
                        "test_id": "B102",
                    },
                    {
                        "issue_severity": "MEDIUM",
                        "issue_text": "Weak crypto",
                        "filename": "src/crypto.py",
                        "line_number": 10,
                        "test_id": "B304",
                    },
                ],
                "metrics": {
                    "_totals": {
                        "SEVERITY.HIGH": 1,
                        "SEVERITY.MEDIUM": 1,
                        "SEVERITY.LOW": 0,
                    }
                },
            }
        )

        mock_run = MagicMock(return_value=mock_result)
        monkeypatch.setattr(subprocess, "run", mock_run)

        rule = SecurityRule()
        result = rule.check(tmp_path)

        assert len(result.details["top_issues"]) == 2
        assert result.details["top_issues"][0]["severity"] == "HIGH"
        assert result.details["top_issues"][0]["code"] == "B102"

    def test_fix_hint_provided(self, tmp_path: Path, monkeypatch):
        """Should provide fix hint when issues found."""
        src_path = tmp_path / "src"
        src_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = json.dumps(
            {
                "results": [{"issue_severity": "HIGH", "issue_text": "Use of exec()"}],
                "metrics": {
                    "_totals": {
                        "SEVERITY.HIGH": 1,
                        "SEVERITY.MEDIUM": 0,
                        "SEVERITY.LOW": 0,
                    }
                },
            }
        )

        mock_run = MagicMock(return_value=mock_result)
        monkeypatch.setattr(subprocess, "run", mock_run)

        rule = SecurityRule()
        result = rule.check(tmp_path)

        assert result.fix_hint is not None
        assert "bandit" in result.fix_hint.lower()

    def test_json_decode_error_handling(self, tmp_path: Path, monkeypatch):
        """Should handle invalid JSON gracefully."""
        src_path = tmp_path / "src"
        src_path.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = "invalid json"

        mock_run = MagicMock(return_value=mock_result)
        monkeypatch.setattr(subprocess, "run", mock_run)

        rule = SecurityRule()
        result = rule.check(tmp_path)

        # Should default to 0 issues
        assert result.details["score"] == 100
        assert result.passed
