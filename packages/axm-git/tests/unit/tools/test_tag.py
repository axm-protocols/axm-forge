"""Unit tests for axm_git.tools.tag (no real I/O)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from axm_git.tools import tag as tag_mod
from axm_git.tools.tag import GitTagTool, _check_ci, _verify_hatch_vcs


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


class TestGitTagToolUnit:
    """Unit-scope tests for GitTagTool (mocked I/O only)."""

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
    @patch("axm_git.tools.tag._check_ci", return_value="red")
    def test_ci_red_blocks(self, _ci: MagicMock, mock_git: MagicMock) -> None:
        """CI red prevents tagging."""
        mock_git.return_value = _mock_completed("")  # clean status
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "CI is red" in (result.error or "")


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
