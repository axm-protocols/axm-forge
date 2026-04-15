from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from axm_git.tools.commit_preflight import GitPreflightTool

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

MODULE = "axm_git.tools.commit_preflight"


@pytest.fixture()
def tool() -> GitPreflightTool:
    return GitPreflightTool()


def _git_result(stdout: str = "", stderr: str = "", rc: int = 0) -> SimpleNamespace:
    return SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_pathspec_subpackage(tool: GitPreflightTool, mocker: MockerFixture) -> None:
    """When path is a subdirectory of git root, run_git includes pathspec."""
    mocker.patch(f"{MODULE}.find_git_root", return_value=Path("/workspace"))
    mock_run = mocker.patch(
        f"{MODULE}.run_git",
        return_value=_git_result(stdout="M  packages/pkg-a/foo.py\n"),
    )

    tool.execute(path="/workspace/packages/pkg-a")

    # Every run_git call should end with the pathspec suffix
    for c in mock_run.call_args_list:
        cmd = c[0][0]
        assert cmd[-2:] == ["--", "packages/pkg-a"], (
            f"Expected pathspec suffix, got cmd={cmd}"
        )


def test_pathspec_root(tool: GitPreflightTool, mocker: MockerFixture) -> None:
    """When path equals git root, no pathspec is added."""
    mocker.patch(f"{MODULE}.find_git_root", return_value=Path("/workspace"))
    mock_run = mocker.patch(
        f"{MODULE}.run_git",
        return_value=_git_result(),
    )

    tool.execute(path="/workspace")

    for c in mock_run.call_args_list:
        cmd = c[0][0]
        assert "--" not in cmd, f"Unexpected pathspec in cmd={cmd}"


def test_dirty_tree(tool: GitPreflightTool, mocker: MockerFixture) -> None:
    """Dirty tree returns files, diff_stat, and diff content."""
    mocker.patch(f"{MODULE}.find_git_root", return_value=Path("/workspace"))

    status_out = " M src/foo.py\n?? new.txt\n"
    diff_stat_out = " src/foo.py | 2 +-\n 1 file changed\n"
    diff_out = "diff --git a/src/foo.py b/src/foo.py\n-old\n+new\n"

    results = iter(
        [
            _git_result(stdout=status_out),  # git status --porcelain
            _git_result(stdout=diff_stat_out),  # git diff --stat
            _git_result(stdout=diff_out),  # git diff -U2
        ]
    )
    mocker.patch(f"{MODULE}.run_git", side_effect=lambda *a, **kw: next(results))

    result = tool.execute(path="/workspace")

    assert result.success is True
    assert result.data["file_count"] == 2
    assert result.data["clean"] is False
    assert result.data["diff_stat"] != ""
    assert result.data["diff"] != ""


def test_clean_tree(tool: GitPreflightTool, mocker: MockerFixture) -> None:
    """Clean tree returns empty files list and clean=True."""
    mocker.patch(f"{MODULE}.find_git_root", return_value=Path("/workspace"))
    mocker.patch(f"{MODULE}.run_git", return_value=_git_result())

    result = tool.execute(path="/workspace")

    assert result.success is True
    assert result.data["file_count"] == 0
    assert result.data["clean"] is True
    assert result.data["diff"] == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_deep_subdir_pathspec(tool: GitPreflightTool, mocker: MockerFixture) -> None:
    """Deep subdirectory produces correct relative pathspec."""
    mocker.patch(f"{MODULE}.find_git_root", return_value=Path("/repo"))
    mock_run = mocker.patch(
        f"{MODULE}.run_git",
        return_value=_git_result(),
    )

    tool.execute(path="/repo/pkg/sub/deep")

    for c in mock_run.call_args_list:
        cmd = c[0][0]
        assert cmd[-2:] == ["--", "pkg/sub/deep"]


def test_git_root_none_falls_through(
    tool: GitPreflightTool, mocker: MockerFixture
) -> None:
    """When find_git_root returns None, not_a_repo_error is triggered."""
    mocker.patch(f"{MODULE}.find_git_root", return_value=None)
    mock_run = mocker.patch(
        f"{MODULE}.run_git",
        return_value=_git_result(rc=128, stderr="fatal: not a git repository"),
    )

    result = tool.execute(path="/not-a-repo")

    assert result.success is False
    # run_git should still be called (fallback) so the not_a_repo_error path fires
    mock_run.assert_called_once()


def test_run_git_receives_git_root_as_cwd(
    tool: GitPreflightTool, mocker: MockerFixture
) -> None:
    """run_git is called with git_root as cwd, not the user-supplied path."""
    mocker.patch(f"{MODULE}.find_git_root", return_value=Path("/workspace"))
    mock_run = mocker.patch(
        f"{MODULE}.run_git",
        return_value=_git_result(),
    )

    tool.execute(path="/workspace/packages/pkg-a")

    for c in mock_run.call_args_list:
        cwd_arg = c[0][1]
        assert cwd_arg == Path("/workspace"), f"Expected git_root as cwd, got {cwd_arg}"
