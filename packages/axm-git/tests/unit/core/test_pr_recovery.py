"""Unit tests for axm_git.core.pr_recovery (no real I/O)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from axm_git.core.pr_recovery import (
    PRRecovery,
    is_already_exists,
    recover_existing_pr,
)


def _gh_proc(
    stdout: str = "",
    stderr: str = "",
    rc: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Build a fake ``gh`` CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["gh"],
        returncode=rc,
        stdout=stdout,
        stderr=stderr,
    )


class TestIsAlreadyExists:
    """is_already_exists detects the 'already exists' signal case-insensitively."""

    @pytest.mark.parametrize(
        "stderr",
        [
            pytest.param("a pull request already exists for branch", id="lower"),
            pytest.param("PR Already Exists", id="mixed_case"),
            pytest.param("ALREADY EXISTS", id="upper"),
        ],
    )
    def test_detects_existing(self, stderr: str) -> None:
        assert is_already_exists(stderr) is True

    @pytest.mark.parametrize(
        "stderr",
        [
            pytest.param("", id="empty"),
            pytest.param("fatal: not a git repository", id="unrelated_error"),
            pytest.param("already pushed", id="partial_no_match"),
        ],
    )
    def test_rejects_other(self, stderr: str) -> None:
        assert is_already_exists(stderr) is False


class TestPRRecoveryModel:
    """PRRecovery.ok reflects whether an error was recorded."""

    def test_ok_when_no_error(self) -> None:
        rec = PRRecovery(url="https://x/1", number="1", already_existed=True)
        assert rec.ok is True

    def test_not_ok_when_error(self) -> None:
        rec = PRRecovery(error="boom")
        assert rec.ok is False


class TestRecoverExistingPr:
    """recover_existing_pr parses the gh JSON or surfaces a retrieval error."""

    @patch("axm_git.core.pr_recovery.run_gh")
    def test_parses_view_json(self, mock_gh: MagicMock) -> None:
        mock_gh.return_value = _gh_proc(
            stdout=json.dumps({"url": "https://x/42", "number": 42})
        )
        rec = recover_existing_pr(Path("/tmp"))
        assert rec.ok is True
        assert rec.url == "https://x/42"
        assert rec.number == "42"
        assert rec.already_existed is True

    @patch("axm_git.core.pr_recovery.run_gh")
    def test_view_failure_returns_error(self, mock_gh: MagicMock) -> None:
        mock_gh.return_value = _gh_proc(stderr="no PR found", rc=1)
        rec = recover_existing_pr(Path("/tmp"))
        assert rec.ok is False
        assert "no PR found" in (rec.error or "")
        assert rec.url == ""
        assert rec.number == ""
