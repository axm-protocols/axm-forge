"""Tests for pre-commit ruff formatting in commit-phase hook."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from axm_git.hooks.commit_phase import CommitPhaseHook, _format_spec_files


def _cp(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a fake CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class TestFormatSpecFiles:
    """Unit tests for _format_spec_files helper."""

    def test_runs_ruff_check_then_format(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Should call ruff check --fix then ruff format on .py files."""
        mock_run = mocker.patch(
            "axm_git.hooks.commit_phase.subprocess.run",
            return_value=_cp(),
        )

        _format_spec_files(["src/foo.py", "src/bar.py"], tmp_path)

        assert mock_run.call_count == 2
        check_call = mock_run.call_args_list[0]
        fmt_call = mock_run.call_args_list[1]

        assert check_call[0][0][0:3] == ["ruff", "check", "--fix"]
        assert fmt_call[0][0][0:2] == ["ruff", "format"]

    def test_skips_non_python_files(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Should not invoke ruff when no .py files in the list."""
        mock_run = mocker.patch(
            "axm_git.hooks.commit_phase.subprocess.run",
        )

        _format_spec_files(["README.md", "config.yaml"], tmp_path)

        mock_run.assert_not_called()

    def test_tolerates_ruff_not_found(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Should log and return gracefully when ruff is not installed."""
        mocker.patch(
            "axm_git.hooks.commit_phase.subprocess.run",
            side_effect=FileNotFoundError("ruff"),
        )

        _format_spec_files(["src/foo.py"], tmp_path)
        # No exception raised

    def test_tolerates_ruff_failure(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """Should continue when ruff exits with non-zero code."""
        mocker.patch(
            "axm_git.hooks.commit_phase.subprocess.run",
            return_value=_cp(returncode=1, stderr="ruff error"),
        )

        _format_spec_files(["src/foo.py"], tmp_path)
        # No exception raised, both commands attempted


class TestCommitFromOutputsCallsFormat:
    """Integration: _commit_from_outputs calls _format_spec_files before staging."""

    @pytest.fixture()
    def hook(self) -> CommitPhaseHook:
        return CommitPhaseHook()

    @pytest.fixture()
    def context(self, tmp_path: Path) -> dict[str, Any]:
        return {
            "working_dir": str(tmp_path),
            "commit_spec": {
                "message": "feat: test format integration",
                "files": ["src/foo.py"],
            },
        }

    def test_format_called_before_stage(
        self,
        hook: CommitPhaseHook,
        context: dict[str, Any],
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """_format_spec_files must run before _stage_spec_files."""
        call_order: list[str] = []

        def track_format(*args: Any, **kwargs: Any) -> None:
            call_order.append("format")

        def track_stage(*args: Any, **kwargs: Any) -> str | None:
            call_order.append("stage")
            return None

        mocker.patch(
            "axm_git.hooks.commit_phase._format_spec_files",
            side_effect=track_format,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            side_effect=track_stage,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase.find_git_root",
            return_value=tmp_path,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            side_effect=[
                _cp(stdout="src/foo.py\n"),  # diff --cached
                _cp(returncode=0),  # commit
                _cp(stdout="abc1234\n"),  # rev-parse
            ],
        )

        result = hook.execute(context, from_outputs=True)

        assert result.success
        assert call_order == ["format", "stage"]
