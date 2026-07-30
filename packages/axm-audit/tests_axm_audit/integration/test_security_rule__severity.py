"""Tests for SecurityRule (Bandit integration)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.security import SecurityRule
from axm_audit.models.results import Severity


def _patch_bandit(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> None:
    """Patch the runner's ``subprocess.Popen`` to simulate a bandit invocation.

    ``run_in_project`` now drives the child via ``Popen.communicate`` instead of
    ``subprocess.run``; the CompletedProcess the rule observes is unchanged.
    """
    proc = MagicMock()
    proc.pid = 4242
    proc.returncode = returncode
    proc.communicate.return_value = (stdout, stderr)
    monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))


def test_no_src_directory(tmp_path: Path) -> None:
    """Should return passing result if src/ doesn't exist."""
    rule = SecurityRule()
    result = rule.check(tmp_path)

    assert result.passed
    assert result.severity == Severity.INFO
    assert "src/ directory not found" in result.message


def test_no_issues_perfect_score(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should return 100/100 if no security issues."""
    src_path = tmp_path / "src"
    src_path.mkdir()
    (src_path / "mod.py").write_text("x = 1\n")

    _patch_bandit(
        monkeypatch,
        stdout=json.dumps(
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
        ),
        returncode=0,
    )

    rule = SecurityRule()
    result = rule.check(tmp_path)

    assert result.passed
    assert result.details is not None
    assert result.score == 100
    assert result.details["high_count"] == 0
    assert result.details["medium_count"] == 0
    assert result.severity == Severity.INFO


def test_high_severity_issues_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should penalize high severity issues heavily (15 points each)."""
    src_path = tmp_path / "src"
    src_path.mkdir()
    (src_path / "mod.py").write_text("x = 1\n")

    # Mock 2 HIGH, 1 MEDIUM issue
    _patch_bandit(
        monkeypatch,
        stdout=json.dumps(
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
        ),
    )

    rule = SecurityRule()
    result = rule.check(tmp_path)

    # Score = 100 - (2*15 + 1*5) = 100 - 35 = 65
    assert result.details is not None
    assert result.score == 65
    assert result.details["high_count"] == 2
    assert result.details["medium_count"] == 1
    assert not result.passed  # < 80
    assert result.severity == Severity.WARNING


def test_bandit_not_found_graceful(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should return graceful failure when bandit binary is unavailable."""
    src_path = tmp_path / "src"
    src_path.mkdir()
    (src_path / "mod.py").write_text("x = 1\n")

    monkeypatch.setattr(
        subprocess,
        "Popen",
        MagicMock(side_effect=FileNotFoundError("bandit")),
    )

    rule = SecurityRule()
    result = rule.check(tmp_path)

    assert not result.passed
    assert "bandit not available" in result.message
    assert result.severity == Severity.ERROR
    assert result.fix_hint is not None
    assert "uv add --dev bandit" in result.fix_hint
    assert result.details is not None
    assert result.score == 0


def test_bandit_crash_not_false_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bandit crash (rc>=2, empty stdout) must NOT produce false positive."""
    src_path = tmp_path / "src"
    src_path.mkdir()
    (src_path / "mod.py").write_text("x = 1\n")

    _patch_bandit(
        monkeypatch,
        stdout="",
        stderr="bandit: error: configuration problem",
        returncode=2,
    )

    rule = SecurityRule()
    result = rule.check(tmp_path)

    assert not result.passed
    assert "bandit failed" in result.message
    assert "rc=2" in result.message
    assert result.severity == Severity.ERROR
    assert result.details is not None
    assert result.score == 0
