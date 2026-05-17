"""Split from ``test_tag.py``."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_git.tools.tag import (
    GitTagTool,
)


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

    @pytest.mark.parametrize(
        ("version_input", "expected_tag"),
        [
            pytest.param("v9.0.0", "v9.0.0", id="with_v_prefix"),
            pytest.param("2.0.0", "v2.0.0", id="no_v_prefix_added"),
        ],
    )
    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    def test_version_override(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
        version_input: str,
        expected_tag: str,
    ) -> None:
        """Explicit version override produces expected tag.

        Adds v prefix if missing.
        """

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
        result = GitTagTool().execute(path="/tmp/test", version=version_input)
        assert result.success
        assert result.data["tag"] == expected_tag

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


class TestTagPrefixExecution:
    """Regression tests for tag prefix in execute()."""

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    @patch("axm_git.tools.tag._get_tag_prefix", return_value="git/")
    def test_tag_execute_uses_prefix(
        self,
        _prefix: MagicMock,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Tag is created with prefix from tag-pattern."""
        created_tags: list[str] = []

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("")  # no existing tags
            if args[0] == "log":
                return _mock_completed("abc feat: init")
            if args[0] == "tag" and "-a" in args:
                created_tags.append(args[2])  # capture the tag name
                return _mock_completed("")
            if args[0] == "push":
                return _mock_completed("")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert created_tags == ["git/v0.1.0"]
        assert result.data["tag"] == "v0.1.0"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag.detect_package_name", return_value=None)
    @patch("axm_git.tools.tag._get_tag_prefix", return_value="")
    def test_tag_execute_standalone_no_prefix(
        self,
        _prefix: MagicMock,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Standalone repo (no tag-pattern) creates plain v* tags."""
        created_tags: list[str] = []

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "status":
                return _mock_completed("")
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.7.0")
            if args[0] == "log":
                return _mock_completed("abc feat: new api")
            if args[0] == "tag" and "-a" in args:
                created_tags.append(args[2])
                return _mock_completed("")
            if args[0] == "push":
                return _mock_completed("")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert created_tags == ["v0.8.0"]
        assert result.data["tag"] == "v0.8.0"
