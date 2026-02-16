"""Tests for get_phase_commit utility."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from axm_git.core.phase_commit import get_phase_commit


class TestGetPhaseCommit:
    """Tests for get_phase_commit."""

    @patch("axm_git.core.phase_commit.run_git")
    def test_found(self, mock_git: MagicMock, tmp_path: Path) -> None:
        """Returns short hash when matching commit exists."""
        (tmp_path / ".git").mkdir()
        mock_git.return_value = MagicMock(stdout="abc1234\n")
        result = get_phase_commit(tmp_path, "verify")
        assert result == "abc1234"
        call_args = mock_git.call_args[0][0]
        assert "--grep" in call_args
        assert "[axm] verify" in call_args

    @patch("axm_git.core.phase_commit.run_git")
    def test_not_found(self, mock_git: MagicMock, tmp_path: Path) -> None:
        """Returns None when no matching commit."""
        (tmp_path / ".git").mkdir()
        mock_git.return_value = MagicMock(stdout="")
        result = get_phase_commit(tmp_path, "nonexistent")
        assert result is None

    def test_not_git_repo(self, tmp_path: Path) -> None:
        """Returns None if .git directory doesn't exist."""
        result = get_phase_commit(tmp_path, "verify")
        assert result is None

    @patch("axm_git.core.phase_commit.run_git")
    def test_custom_format(self, mock_git: MagicMock, tmp_path: Path) -> None:
        """Custom message_format is used for searching."""
        (tmp_path / ".git").mkdir()
        mock_git.return_value = MagicMock(stdout="def5678\n")
        result = get_phase_commit(tmp_path, "plan", message_format="AXM-{phase}")
        assert result == "def5678"
        call_args = mock_git.call_args[0][0]
        assert "AXM-plan" in call_args
