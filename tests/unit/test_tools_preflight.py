"""Unit tests for GitPreflightTool."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.tools.commit_preflight import GitPreflightTool


class TestGitPreflightTool:
    """Test GitPreflightTool behavior."""

    def test_name(self) -> None:
        tool = GitPreflightTool()
        assert tool.name == "git_preflight"

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_clean_tree(self, mock_git: MagicMock) -> None:
        mock_git.return_value = subprocess.CompletedProcess(
            args=["git"],
            returncode=0,
            stdout="",
            stderr="",
        )
        result = GitPreflightTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["clean"] is True
        assert result.data["files"] == []

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_dirty_tree(self, mock_git: MagicMock) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if "--porcelain" in args:
                return subprocess.CompletedProcess(
                    args=["git"],
                    returncode=0,
                    stdout=" M README.md\n?? newfile.py\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=["git"],
                returncode=0,
                stdout=" 1 file changed, +5 -2\n",
                stderr="",
            )

        mock_git.side_effect = _side_effect
        result = GitPreflightTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["clean"] is False
        assert len(result.data["files"]) == 2
        assert result.data["files"][0]["path"] == "README.md"
        assert result.data["files"][0]["status"] == "M"

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_git_failure(self, mock_git: MagicMock) -> None:
        mock_git.return_value = subprocess.CompletedProcess(
            args=["git"],
            returncode=128,
            stdout="",
            stderr="not a git repository",
        )
        result = GitPreflightTool().execute(path="/tmp/bad")
        assert not result.success
        assert "git status failed" in (result.error or "")
