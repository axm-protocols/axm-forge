"""Unit tests for GitPreflightTool."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from axm_git.tools.commit_preflight import GitPreflightTool, render_text


def _completed(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _git_result(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


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
        assert result.data["diff_stat"] == ""
        assert result.data["diff_truncated"] is False
        # diff --stat must not be called on a clean repo
        called_cmds = [c.args[0] for c in mock_git.call_args_list]
        assert not any("--stat" in cmd for cmd in called_cmds)

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
        assert "not a git repository" in (result.error or "")

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

    @patch("axm_git.core.runner.suggest_git_repos")
    @patch("axm_git.tools.commit_preflight.run_git")
    def test_not_git_repo_with_suggestions(
        self, mock_git: MagicMock, mock_suggest: MagicMock
    ) -> None:
        mock_git.return_value = _completed(
            returncode=128, stderr="fatal: not a git repository"
        )
        mock_suggest.return_value = ["axm-ast", "axm-core"]
        result = GitPreflightTool().execute(path="/tmp/mono")
        assert not result.success
        assert "not a git repository" in (result.error or "")
        assert result.data is not None
        assert result.data["suggestions"] == ["axm-ast", "axm-core"]

    @patch("axm_git.core.runner.suggest_git_repos")
    @patch("axm_git.tools.commit_preflight.run_git")
    def test_not_git_repo_no_suggestions(
        self, mock_git: MagicMock, mock_suggest: MagicMock
    ) -> None:
        mock_git.return_value = _completed(
            returncode=128, stderr="fatal: not a git repository"
        )
        mock_suggest.return_value = []
        result = GitPreflightTool().execute(path="/tmp/empty")
        assert not result.success
        assert "not a git repository" in (result.error or "")

    @patch("axm_git.tools.commit_preflight.run_git")
    def test_no_hint_in_result(self, mock_git: MagicMock) -> None:
        mock_git.return_value = _completed(stdout=" M README.md\n")
        result = GitPreflightTool().execute(path="/tmp/test")
        assert result.success
        assert getattr(result, "hint", None) is None


# ---------------------------------------------------------------------------
# _render_text + execute helpers (formerly tests/unit/test_commit_preflight.py)
# ---------------------------------------------------------------------------


@pytest.fixture()
def tool() -> GitPreflightTool:
    return GitPreflightTool()


def test_render_text_clean() -> None:
    result = render_text(
        files=[], diff_stat="", diff="", diff_truncated=False, max_diff_lines=200
    )
    assert result == "git_preflight | clean"


def test_render_text_dirty() -> None:
    files = [
        {"path": "src/foo.py", "status": "M"},
        {"path": "src/bar.py", "status": "A"},
    ]
    diff_stat = " 2 files changed, 10 insertions(+), 3 deletions(-)"
    diff = "diff --git a/src/foo.py b/src/foo.py\n--- a/src/foo.py\n+++ b/src/foo.py"
    result = render_text(
        files=files,
        diff_stat=diff_stat,
        diff=diff,
        diff_truncated=False,
        max_diff_lines=200,
    )
    assert "git_preflight | 2 files · dirty" in result
    assert "M  src/foo.py" in result
    assert "A  src/bar.py" in result
    assert diff_stat in result
    assert diff in result


def test_render_text_nodiff() -> None:
    files = [{"path": "src/foo.py", "status": "M"}]
    diff_stat = " 1 file changed, 5 insertions(+)"
    result = render_text(
        files=files,
        diff_stat=diff_stat,
        diff="",
        diff_truncated=False,
        max_diff_lines=200,
    )
    assert "git_preflight | 1 files · dirty" in result
    assert "M  src/foo.py" in result
    assert diff_stat in result
    assert "diff --git" not in result


def test_render_text_truncated() -> None:
    files = [{"path": "src/foo.py", "status": "M"}]
    diff = "diff --git a/src/foo.py b/src/foo.py"
    result = render_text(
        files=files,
        diff_stat=" 1 file changed",
        diff=diff,
        diff_truncated=True,
        max_diff_lines=200,
    )
    assert result.endswith("[diff truncated at 200 lines]")


def test_render_text_file_status_format() -> None:
    files = [{"path": "src/mod.py", "status": "M"}]
    result = render_text(
        files=files,
        diff_stat="",
        diff="",
        diff_truncated=False,
        max_diff_lines=200,
    )
    lines = result.splitlines()
    file_line = next(ln for ln in lines if "src/mod.py" in ln)
    assert file_line.startswith("M  ")


def test_render_text_untracked_format() -> None:
    files = [{"path": "new_file.py", "status": "??"}]
    result = render_text(
        files=files,
        diff_stat="",
        diff="",
        diff_truncated=False,
        max_diff_lines=200,
    )
    lines = result.splitlines()
    file_line = next(ln for ln in lines if "new_file.py" in ln)
    assert file_line.startswith("?? ")


def _mock_run_git_dirty(cmd: list[str], cwd: Any) -> SimpleNamespace:
    if cmd[0] == "status":
        return _git_result(stdout=" M src/foo.py\n")
    if cmd[0] == "diff" and "-U2" in cmd:
        return _git_result(stdout="diff --git a/src/foo.py b/src/foo.py")
    return _git_result(stdout=" 1 file changed, 2 insertions(+)")


def test_execute_sets_text(
    tool: GitPreflightTool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("axm_git.tools.commit_preflight.find_git_root", lambda p: p)
    monkeypatch.setattr("axm_git.tools.commit_preflight.run_git", _mock_run_git_dirty)
    result = tool.execute(path="/tmp/repo")
    assert result.text is not None
    assert isinstance(result.text, str)


def test_execute_preserves_data(
    tool: GitPreflightTool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("axm_git.tools.commit_preflight.find_git_root", lambda p: p)
    monkeypatch.setattr("axm_git.tools.commit_preflight.run_git", _mock_run_git_dirty)
    result = tool.execute(path="/tmp/repo")
    assert "files" in result.data
    assert "clean" in result.data
    assert "diff" in result.data
    assert result.data["clean"] is False
    assert len(result.data["files"]) == 1
    assert result.data["files"][0]["path"] == "src/foo.py"
    assert result.data["files"][0]["status"] == "M"


def test_execute_clean_text(
    tool: GitPreflightTool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("axm_git.tools.commit_preflight.find_git_root", lambda p: p)
    monkeypatch.setattr(
        "axm_git.tools.commit_preflight.run_git",
        lambda cmd, cwd: _git_result(stdout=""),
    )
    result = tool.execute(path="/tmp/repo")
    assert result.text == "git_preflight | clean"


def test_render_text_empty_diff_stat() -> None:
    """Clean repo — no blank stat section in text."""
    result = render_text(
        files=[], diff_stat="", diff="", diff_truncated=False, max_diff_lines=200
    )
    assert result == "git_preflight | clean"
    assert "\n\n\n" not in result


def test_render_text_single_file() -> None:
    """Single changed file — header shows '1 files · dirty'."""
    files = [{"path": "README.md", "status": "M"}]
    result = render_text(
        files=files, diff_stat="", diff="", diff_truncated=False, max_diff_lines=200
    )
    assert "1 files · dirty" in result


def test_render_text_long_file_paths() -> None:
    """200+ char paths shown in full, no truncation."""
    long_path = "a" * 210 + ".py"
    files = [{"path": long_path, "status": "M"}]
    result = render_text(
        files=files, diff_stat="", diff="", diff_truncated=False, max_diff_lines=200
    )
    assert long_path in result


class TestDiffLinesZeroCleanTree:
    """AC1 + AC3: clean repo with diff_lines=0 skips diff --stat subprocess."""

    def test_clean_tree(self, tool: GitPreflightTool, mocker: MockerFixture) -> None:
        mock_run = mocker.patch(
            "axm_git.tools.commit_preflight.run_git",
            return_value=_git_result(stdout=""),
        )

        result = tool.execute(path="/tmp/repo", diff_lines=0)

        assert result.success is True
        mock_run.assert_called_once()
        assert result.data["diff_stat"] == ""
        assert result.data["clean"] is True


class TestDiffLinesZeroDirtyTree:
    """Verify dirty tree with diff_lines=0 still populates diff_stat."""

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


class TestDiffLinesZeroNoHint:
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


class TestDiffLinesZeroCleanRepoPerf:
    """Edge: clean repo must not spawn git diff --stat subprocess."""

    def test_no_diff_stat_call_when_clean(
        self, tool: GitPreflightTool, mocker: MockerFixture
    ) -> None:
        mock_run = mocker.patch(
            "axm_git.tools.commit_preflight.run_git",
            return_value=_git_result(stdout=""),
        )

        tool.execute(path="/tmp/repo", diff_lines=0)

        assert mock_run.call_count == 1
        args = mock_run.call_args[0][0]
        assert args[0] == "status"
