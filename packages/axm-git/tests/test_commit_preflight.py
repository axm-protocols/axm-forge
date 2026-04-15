from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from axm_git.tools.commit_preflight import GitPreflightTool

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _git_result(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


@pytest.fixture
def tool() -> GitPreflightTool:
    return GitPreflightTool()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestCleanTree:
    """AC1 + AC3: clean repo returns diff_stat='' without spawning diff --stat."""

    def test_clean_tree(self, tool: GitPreflightTool, mocker: MockerFixture) -> None:
        mock_run = mocker.patch(
            "axm_git.tools.commit_preflight.run_git",
            return_value=_git_result(stdout=""),
        )

        result = tool.execute(path="/tmp/repo", diff_lines=0)

        assert result.success is True
        # Only 'git status --porcelain' — no diff subprocess spawned
        mock_run.assert_called_once()
        assert result.data["diff_stat"] == ""
        assert result.data["clean"] is True


class TestDirtyTree:
    """Verify dirty tree still populates diff_stat (unchanged behavior)."""

    def test_dirty_tree(self, tool: GitPreflightTool, mocker: MockerFixture) -> None:
        status_out = " M src/foo.py\n?? newfile.txt"
        diff_stat_out = " src/foo.py | 3 ++-\n 1 file changed"

        def side_effect(args: list[str], cwd: object) -> SimpleNamespace:
            if args[0] == "status":
                return _git_result(stdout=status_out)
            if args[:2] == ["diff", "--stat"]:
                return _git_result(stdout=diff_stat_out)
            return _git_result()

        mocker.patch(
            "axm_git.tools.commit_preflight.run_git",
            side_effect=side_effect,
        )

        result = tool.execute(path="/tmp/repo", diff_lines=0)

        assert result.success is True
        assert result.data["diff_stat"] == diff_stat_out.strip()
        assert result.data["file_count"] == 2
        assert result.data["clean"] is False


class TestNoHintInResult:
    """AC2: hint parameter must not appear on ToolResult."""

    def test_no_hint_in_result(
        self, tool: GitPreflightTool, mocker: MockerFixture
    ) -> None:
        mocker.patch(
            "axm_git.tools.commit_preflight.run_git",
            return_value=_git_result(stdout=""),
        )

        result = tool.execute(path="/tmp/repo", diff_lines=0)

        assert getattr(result, "hint", None) is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCleanRepoPerf:
    """Edge: clean repo must not spawn git diff --stat subprocess."""

    def test_no_diff_stat_call_when_clean(
        self, tool: GitPreflightTool, mocker: MockerFixture
    ) -> None:
        mock_run = mocker.patch(
            "axm_git.tools.commit_preflight.run_git",
            return_value=_git_result(stdout=""),
        )

        tool.execute(path="/tmp/repo", diff_lines=0)

        # Exactly one call: status --porcelain
        assert mock_run.call_count == 1
        args = mock_run.call_args[0][0]
        assert args[0] == "status"
