"""Unit tests for tag.py private helpers: _check_ci, _verify_hatch_vcs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# ── _check_ci ──────────────────────────────────────────────────────────


class TestCheckCi:
    """Test the _check_ci helper."""

    @patch("axm_git.tools.tag.gh_available", return_value=False)
    def test_skipped_when_gh_unavailable(self, _gh: MagicMock) -> None:
        from axm_git.tools.tag import _check_ci

        assert _check_ci(Path("/tmp")) == "skipped"

    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_green(self, _gh: MagicMock, mock_gh: MagicMock) -> None:
        from axm_git.tools.tag import _check_ci

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
        from axm_git.tools.tag import _check_ci

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
        from axm_git.tools.tag import _check_ci

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
        from axm_git.tools.tag import _check_ci

        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="[]", stderr=""
        )
        assert _check_ci(Path("/tmp")) == "skipped"

    @patch("axm_git.tools.tag.run_gh")
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_gh_returncode_nonzero(self, _gh: MagicMock, mock_gh: MagicMock) -> None:
        from axm_git.tools.tag import _check_ci

        mock_gh.return_value = subprocess.CompletedProcess(
            args=["gh"], returncode=1, stdout="", stderr="error"
        )
        assert _check_ci(Path("/tmp")) == "skipped"

    @patch("axm_git.tools.tag.run_gh", side_effect=FileNotFoundError)
    @patch("axm_git.tools.tag.gh_available", return_value=True)
    def test_exception_returns_error(self, _gh: MagicMock, _mock_gh: MagicMock) -> None:
        from axm_git.tools.tag import _check_ci

        assert _check_ci(Path("/tmp")) == "error"


# ── _verify_hatch_vcs ─────────────────────────────────────────────────


class TestVerifyHatchVcs:
    """Test the _verify_hatch_vcs helper."""

    @patch("axm_git.tools.tag.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        from axm_git.tools.tag import _verify_hatch_vcs

        def _side_effect(
            args: list[str], **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if "sync" in args:
                return subprocess.CompletedProcess(
                    args=args, returncode=0, stdout="", stderr=""
                )
            # version check
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout="0.8.0\n", stderr=""
            )

        mock_run.side_effect = _side_effect
        assert _verify_hatch_vcs(Path("/tmp"), "my-pkg") == "0.8.0"

    @patch("axm_git.tools.tag.subprocess.run")
    def test_sync_fails(self, mock_run: MagicMock) -> None:
        from axm_git.tools.tag import _verify_hatch_vcs

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        assert _verify_hatch_vcs(Path("/tmp"), "my-pkg") is None

    @patch("axm_git.tools.tag.subprocess.run")
    def test_version_check_fails(self, mock_run: MagicMock) -> None:
        from axm_git.tools.tag import _verify_hatch_vcs

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
        from axm_git.tools.tag import _verify_hatch_vcs

        assert _verify_hatch_vcs(Path("/tmp"), "my-pkg") is None
