"""Unit tests for GitTagTool."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.tools.tag import GitTagTool


def _mock_completed(
    stdout: str = "",
    stderr: str = "",
    rc: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Create a mock CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=rc,
        stdout=stdout,
        stderr=stderr,
    )


class TestGitTagTool:
    """Test GitTagTool behavior."""

    def test_name(self) -> None:
        tool = GitTagTool()
        assert tool.name == "git_tag"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    def test_dirty_tree(self, _gh: MagicMock, mock_git: MagicMock) -> None:
        mock_git.return_value = _mock_completed("M src/foo.py")
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "Uncommitted" in (result.error or "")

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    def test_no_commits(self, _gh: MagicMock, mock_git: MagicMock) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag":
                return _mock_completed("v0.7.0\nv0.6.0")
            if args[0] == "log":
                return _mock_completed("")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "No commits" in (result.error or "")

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    def test_success_auto_version(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.7.0")
            if args[0] == "log":
                return _mock_completed("abc feat: new api\ndef fix: bug")
            if args[0] == "tag" and "-a" in args:
                return _mock_completed("", rc=0)
            if args[0] == "push":
                return _mock_completed("", rc=0)
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["tag"] == "v0.8.0"
        assert result.data["bump"] == "minor"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    def test_version_override(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.7.0")
            if args[0] == "log":
                return _mock_completed("abc fix: bug")
            if args[0] == "tag" and "-a" in args:
                return _mock_completed("", rc=0)
            if args[0] == "push":
                return _mock_completed("", rc=0)
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test", version="v9.0.0")
        assert result.success
        assert result.data["tag"] == "v9.0.0"
        assert result.data["bump"] == "override"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    def test_version_override_no_v_prefix(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Version without v prefix gets it added."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.1.0")
            if args[0] == "log":
                return _mock_completed("abc fix: x")
            if args[0] == "tag" and "-a" in args:
                return _mock_completed("", rc=0)
            if args[0] == "push":
                return _mock_completed("", rc=0)
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test", version="2.0.0")
        assert result.success
        assert result.data["tag"] == "v2.0.0"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    def test_no_existing_tags(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """First tag ever — base is v0.0.0."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("")  # no tags
            if args[0] == "log":
                return _mock_completed("abc feat: init")
            if args[0] == "tag" and "-a" in args:
                return _mock_completed("")
            if args[0] == "push":
                return _mock_completed("")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["tag"] == "v0.1.0"
        assert result.data["current_tag"] == "none"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    def test_tag_create_failure(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Tag creation failure reports error."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.1.0")
            if args[0] == "log":
                return _mock_completed("abc fix: x")
            if args[0] == "tag" and "-a" in args:
                return _mock_completed(stderr="tag already exists", rc=128)
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "Failed to create tag" in (result.error or "")

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag._check_ci", return_value="red")
    def test_ci_red_blocks(self, _ci: MagicMock, mock_git: MagicMock) -> None:
        """CI red prevents tagging."""
        mock_git.return_value = _mock_completed("")  # clean status
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "CI is red" in (result.error or "")

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    def test_push_failure_still_reports(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Tag succeeds even when push fails — pushed=False."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.1.0")
            if args[0] == "log":
                return _mock_completed("abc fix: x")
            if args[0] == "tag" and "-a" in args:
                return _mock_completed("")
            if args[0] == "push":
                return _mock_completed(stderr="rejected", rc=1)
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["pushed"] is False
