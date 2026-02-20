"""Unit tests for GitPreflightTool."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.tools.commit_preflight import GitPreflightTool


def _completed(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


SAMPLE_DIFF = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,3 +1,3 @@
 # hello
-old line
+new line
"""


class TestGitPreflightTool:
    """Test GitPreflightTool behavior."""

    def test_name(self) -> None:
        tool = GitPreflightTool()
        assert tool.name == "git_preflight"

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_clean_tree(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed()
        result = GitPreflightTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["clean"] is True
        assert result.data["files"] == []
        assert result.data["diff"] == ""
        assert result.data["diff_truncated"] is False

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_dirty_tree(self, mock_git: MagicMock) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if "--porcelain" in args:
                return _completed(stdout=" M README.md\n?? newfile.py\n")
            if "--stat" in args:
                return _completed(stdout=" 1 file changed, +5 -2\n")
            return _completed(stdout=SAMPLE_DIFF)

        mock_git.side_effect = _side_effect
        result = GitPreflightTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["clean"] is False
        assert len(result.data["files"]) == 2
        assert result.data["files"][0]["path"] == "README.md"
        assert result.data["files"][0]["status"] == "M"
        assert "new line" in result.data["diff"]
        assert result.data["diff_truncated"] is False

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_git_failure(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(
            returncode=128, stderr="not a git repository"
        )
        result = GitPreflightTool().execute(path="/tmp/bad")
        assert not result.success
        assert "git status failed" in (result.error or "")

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_diff_truncated(self, mock_git: MagicMock) -> None:
        big_diff = "\n".join(f"line {i}" for i in range(300))

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if "--porcelain" in args:
                return _completed(stdout=" M big.py\n")
            if "--stat" in args:
                return _completed(stdout=" 1 file changed\n")
            return _completed(stdout=big_diff)

        mock_git.side_effect = _side_effect
        result = GitPreflightTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["diff_truncated"] is True
        assert result.data["diff"].count("\n") == 199  # 200 lines, 199 newlines

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_diff_disabled(self, mock_git: MagicMock) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if "--porcelain" in args:
                return _completed(stdout=" M README.md\n")
            if "--stat" in args:
                return _completed(stdout=" 1 file changed\n")
            msg = "should not be called"
            raise AssertionError(msg)

        mock_git.side_effect = _side_effect
        result = GitPreflightTool().execute(path="/tmp/test", diff_lines=0)
        assert result.success
        assert result.data["diff"] == ""
        assert result.data["diff_truncated"] is False
