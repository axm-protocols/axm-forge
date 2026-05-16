"""Split from ``test_tag.py``."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.tools.tag import (
    GitTagTool,
    _get_tag_prefix,
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


# ── Tag prefix regression tests (AXM-371) ────────────────────


class TestGetTagPrefix:
    """Regression tests for _get_tag_prefix helper."""

    def test_get_tag_prefix_reads_pattern(self, tmp_path: Path) -> None:
        """Reads tag-pattern and extracts prefix."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.hatch.version]\ntag-pattern = "git/v(?P<version>.*)"\n'
        )
        assert _get_tag_prefix(tmp_path) == "git/"

    def test_get_tag_prefix_no_pattern(self, tmp_path: Path) -> None:
        """Returns empty when no tag-pattern in pyproject."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.hatch.version]\nsource = "vcs"\n')
        assert _get_tag_prefix(tmp_path) == ""

    def test_get_tag_prefix_no_pyproject(self, tmp_path: Path) -> None:
        """Returns empty when pyproject.toml does not exist."""
        assert _get_tag_prefix(tmp_path) == ""


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
