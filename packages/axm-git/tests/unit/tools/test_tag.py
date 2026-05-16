"""Unit tests for GitTagTool and tag.py private helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.tools import tag as tag_mod
from axm_git.tools.tag import (
    GitTagTool,
    _check_ci,
    _get_tag_prefix,
    _verify_hatch_vcs,
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


class TestVerifyHatchVcsTimeouts:
    """AC4 — _verify_hatch_vcs: 600s timeout for uv sync, None on TimeoutExpired."""

    @patch("axm_git.tools.tag.subprocess.run")
    def test_uv_sync_uses_600s_timeout(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1.2.3", stderr=""
        )
        tag_mod._verify_hatch_vcs(tmp_path, "1.2.3")
        uv_sync_calls = [
            c
            for c in mock_run.call_args_list
            if c.args
            and len(c.args[0]) >= 2
            and c.args[0][0] == "uv"
            and c.args[0][1] == "sync"
        ]
        assert uv_sync_calls, "uv sync was not invoked"
        assert uv_sync_calls[0].kwargs.get("timeout") == 600

    @patch(
        "axm_git.tools.tag.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["uv", "sync"], timeout=600),
    )
    def test_returns_none_on_uv_sync_timeout(
        self, _mock_run: MagicMock, tmp_path: Path
    ) -> None:
        assert tag_mod._verify_hatch_vcs(tmp_path, "1.2.3") is None


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


# ── Tag prefix regression tests (AXM-371) ────────────────────────────


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


# --- Tests for tag helpers (_check_ci, _verify_hatch_vcs) ---
# Folded from tests/unit/test_tag_helpers.py during /mirror-fix.


class TestCheckCi:
    """Test the _check_ci helper."""

    @patch("axm_git.tools.tag.gh_available", return_value=False)
    def test_skipped_when_gh_unavailable(self, _gh: MagicMock) -> None:
        assert _check_ci(Path("/tmp")) == "skipped"

    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_green(self, _gh: MagicMock, mock_gh: MagicMock) -> None:
        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"],
            returncode=0,
            stdout=json.dumps([{"conclusion": "success", "status": "completed"}]),
            stderr="",
        )
        assert _check_ci(Path("/tmp")) == "green"

    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_pending(self, _gh: MagicMock, mock_gh: MagicMock) -> None:
        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"],
            returncode=0,
            stdout=json.dumps([{"conclusion": None, "status": "in_progress"}]),
            stderr="",
        )
        assert _check_ci(Path("/tmp")) == "pending"

    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_red(self, _gh: MagicMock, mock_gh: MagicMock) -> None:
        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"],
            returncode=0,
            stdout=json.dumps([{"conclusion": "failure", "status": "completed"}]),
            stderr="",
        )
        assert _check_ci(Path("/tmp")) == "red"

    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_empty_runs(self, _gh: MagicMock, mock_gh: MagicMock) -> None:
        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="[]", stderr=""
        )
        assert _check_ci(Path("/tmp")) == "skipped"

    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_gh_returncode_nonzero(self, _gh: MagicMock, mock_gh: MagicMock) -> None:
        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=1, stdout="", stderr="error"
        )
        assert _check_ci(Path("/tmp")) == "skipped"

    @patch("axm_git.tools.tag.run_gh", side_effect=FileNotFoundError)
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_exception_returns_error(self, _gh: MagicMock, _mock_gh: MagicMock) -> None:
        assert _check_ci(Path("/tmp")) == "error"


class TestVerifyHatchVcs:
    """Test the _verify_hatch_vcs helper."""

    @patch("axm_git.tools.tag.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        def _side_effect(
            args: list[str], **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if "sync" in args:
                return subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout="0.8.0\n", stderr=""
            )

        mock_run.side_effect = _side_effect
        assert _verify_hatch_vcs(Path("/tmp"), "my-pkg") == "0.8.0"

    @patch("axm_git.tools.tag.subprocess.run")
    def test_sync_fails(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        assert _verify_hatch_vcs(Path("/tmp"), "my-pkg") is None

    @patch("axm_git.tools.tag.subprocess.run")
    def test_version_check_fails(self, mock_run: MagicMock) -> None:
        call_count = 0

        def _side_effect(
            args: list[str], **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=args, returncode=1, stdout="", stderr=""
            )

        mock_run.side_effect = _side_effect
        assert _verify_hatch_vcs(Path("/tmp"), "my-pkg") is None

    @patch(
        "axm_git.tools.tag.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_uv_not_found(self, _mock: MagicMock) -> None:
        assert _verify_hatch_vcs(Path("/tmp"), "my-pkg") is None
