"""Split from ``test_bandit_security_scan.py``."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_audit.core.rules.security import SecurityRule


def test_top_issues_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    assert result.details is not None
    assert len(result.details["top_issues"]) == 2
    assert result.details["top_issues"][0]["severity"] == "HIGH"
    assert result.details["top_issues"][0]["code"] == "B102"


def test_fix_hint_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_json_decode_error_handling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should handle invalid JSON gracefully."""
    src_path = tmp_path / "src"
    src_path.mkdir()

    mock_result = MagicMock()
    mock_result.stdout = "invalid json"
    mock_result.returncode = 1

    mock_run = MagicMock(return_value=mock_result)
    monkeypatch.setattr(subprocess, "run", mock_run)

    rule = SecurityRule()
    result = rule.check(tmp_path)

    # Should default to 0 issues
    assert result.details is not None
    assert result.score == 100
    assert result.passed


def test_bandit_issues_rc1_still_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bandit rc=1 with valid JSON still reports issues normally."""
    src_path = tmp_path / "src"
    src_path.mkdir()

    mock_result = MagicMock()
    mock_result.stdout = json.dumps(
        {
            "results": [
                {"issue_severity": "HIGH", "issue_text": "exec() call"},
            ],
        }
    )
    mock_result.returncode = 1

    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=mock_result))

    rule = SecurityRule()
    result = rule.check(tmp_path)

    assert result.details is not None
    assert result.details["high_count"] == 1
    assert result.score == 85  # 100 - 15


def test_bandit_uses_run_in_project(tmp_path: Path) -> None:
    """SecurityRule should call run_in_project."""
    from axm_audit.core.rules.security import SecurityRule

    (tmp_path / "src").mkdir()

    with patch("axm_audit.core.rules.security.run_in_project") as mock:
        mock.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
        SecurityRule().check(tmp_path)
        mock.assert_called_once()
        assert mock.call_args[0][0][0] == "bandit"


def test_security_injects_bandit(tmp_path: Path) -> None:
    """SecurityRule passes with_packages=["bandit"]."""
    from axm_audit.core.rules.security import SecurityRule

    (tmp_path / "src").mkdir()

    with patch("axm_audit.core.rules.security.run_in_project") as mock:
        mock.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
        SecurityRule().check(tmp_path)
        assert mock.call_args[1]["with_packages"] == ["bandit"]
