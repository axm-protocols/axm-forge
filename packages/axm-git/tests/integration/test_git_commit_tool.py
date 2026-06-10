"""Integration test for Bug 1 fix: ``auto_fixed_files`` populated correctly.

When a pre-commit hook auto-fixes files, ``data['failed_commit']
['auto_fixed_files']`` must list those files. Previously the diff was
captured *after* re-staging, which always returned an empty list.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration

MODULE = "axm_git.tools.commit"


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)


def _write_executable(target: Path, script: str) -> None:
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_auto_fixed_files_listed_when_hook_rewrites_then_fails(
    tmp_path: Path,
) -> None:
    """Hook rewrites a file and keeps failing — auto_fixed_files must list it."""
    _init_repo(tmp_path)
    target = tmp_path / "a.txt"
    target.write_text("original\n")

    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    # The hook rewrites a.txt every time and exits non-zero with the
    # "files were modified by this hook" sentinel. The retry loop will
    # therefore re-stage and try again, and fail a second time. The
    # captured ``auto_fixed_files`` must contain ``a.txt``.
    _write_executable(
        hook,
        "#!/bin/sh\n"
        f'echo "rewritten" > "{target}"\n'
        'echo "files were modified by this hook" >&2\n'
        "exit 1\n",
    )

    result = GitCommitTool().execute(
        path=str(tmp_path),
        commits=[{"files": ["a.txt"], "message": "feat: add a"}],
    )

    assert result.success is False
    assert result.data is not None
    failed = result.data.get("failed_commit")
    assert failed is not None, result.data
    assert failed["retried"] is True
    assert failed["auto_fixed_files"], (
        f"expected non-empty auto_fixed_files, got {failed['auto_fixed_files']!r}"
    )
    assert "a.txt" in failed["auto_fixed_files"]


def _init_repo__from_git_commit_tool(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    # Initial commit
    readme = path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: init", "--no-verify"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


class TestCommitFlow:
    """Functional tests for git_commit."""

    def test_commit_batch_end_to_end(self, tmp_path: Path) -> None:
        _init_repo__from_git_commit_tool(tmp_path)

        # Create two changes
        (tmp_path / "a.py").write_text("# file a\n")
        (tmp_path / "b.py").write_text("# file b\n")

        result = GitCommitTool().execute(
            path=str(tmp_path),
            commits=[
                {"files": ["a.py"], "message": "feat: add a"},
                {"files": ["b.py"], "message": "fix: add b"},
            ],
        )
        assert result.success
        assert result.data["total"] == 2
        assert result.data["succeeded"] == 2

        # Verify git log
        log = subprocess.run(
            ["git", "log", "--oneline", "-3"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "feat: add a" in log.stdout
        assert "fix: add b" in log.stdout

    @pytest.mark.parametrize(
        "commits",
        [
            [{"files": ["nonexistent.py"], "message": "fix: ghost"}],
        ],
    )
    def test_commit_nonexistent_file(
        self, tmp_path: Path, commits: list[dict[str, object]]
    ) -> None:
        _init_repo__from_git_commit_tool(tmp_path)
        result = GitCommitTool().execute(
            path=str(tmp_path),
            commits=commits,
        )
        # git add on nonexistent file should fail
        assert not result.success

    def test_commit_deleted_file(self, tmp_path: Path) -> None:
        """Committing a deleted file works with git add -A."""
        _init_repo__from_git_commit_tool(tmp_path)

        # Create and commit a file
        target = tmp_path / "to_delete.py"
        target.write_text("# will be deleted\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "chore: add file", "--no-verify"],
            cwd=str(tmp_path),
            capture_output=True,
            check=True,
        )

        # Delete the file from disk
        target.unlink()

        # Commit the deletion via git_commit
        result = GitCommitTool().execute(
            path=str(tmp_path),
            commits=[{"files": ["to_delete.py"], "message": "fix: remove dead file"}],
        )
        assert result.success
        assert result.data["total"] == 1

        # Verify the file is no longer tracked
        ls = subprocess.run(
            ["git", "ls-files", "to_delete.py"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert ls.stdout.strip() == ""


class TestConventionalWarningRealRepo:
    """Warn-by-default conventional validation against a real repo."""

    def test_warns_on_bad_message_real_commit(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """AC1, AC4: a non-conventional message warns yet the commit lands."""
        import logging

        _init_repo__from_git_commit_tool(tmp_path)
        (tmp_path / "a.txt").write_text("hello\n")
        with caplog.at_level(logging.WARNING):
            result = GitCommitTool().execute(
                path=str(tmp_path),
                commits=[{"files": ["a.txt"], "message": "wip stuff"}],
            )
        assert result.success is True
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        assert log.stdout.strip() == "wip stuff"
        assert any(
            "wip stuff" in r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING
        )


# ---------------------------------------------------------------------------
# Mid-batch failure (formerly tests/integration/test_commit.py)
# ---------------------------------------------------------------------------


def _git_result(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Subdir-aware path resolution (AXM-1898): GitCommitTool + stage_spec_files
# ---------------------------------------------------------------------------


def _subdir_run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo_subdir(tmp_path: Path) -> Path:
    """A real git repo with an initial commit and identity configured."""
    _subdir_run(["git", "init"], tmp_path)
    _subdir_run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _subdir_run(["git", "config", "user.name", "Test"], tmp_path)
    _subdir_run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("init\n")
    _subdir_run(["git", "add", "-A"], tmp_path)
    _subdir_run(["git", "commit", "-m", "init"], tmp_path)
    return tmp_path


def _committed_files_subdir(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in out.stdout.strip().splitlines() if line}


class TestSubdirAwareStaging:
    """AC2-AC5: GitCommitTool stages via the promoted subdir-aware resolver."""

    def test_commit_with_package_path_and_root_relative_files(
        self, git_repo_subdir: Path
    ) -> None:
        """AC2: path=<subdir> + git-root-relative files → ok, no dup prefix."""
        pkg = git_repo_subdir / "packages" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "a.py").write_text("x = 1\n")

        result = GitCommitTool().execute(
            path=str(pkg),
            commits=[{"message": "feat: add a", "files": ["packages/pkg/a.py"]}],
        )

        assert result.success, result.error
        assert "packages/pkg/a.py" in _committed_files_subdir(git_repo_subdir)

    def test_commit_with_git_root_path_unchanged(self, git_repo_subdir: Path) -> None:
        """AC3: path=<git-root>, git-root-relative files stages exactly those."""
        (git_repo_subdir / "b.py").write_text("y = 2\n")

        result = GitCommitTool().execute(
            path=str(git_repo_subdir),
            commits=[{"message": "feat: add b", "files": ["b.py"]}],
        )

        assert result.success, result.error
        assert _committed_files_subdir(git_repo_subdir) == {"b.py"}

    def test_commit_stages_tracked_deletion_from_package_path(
        self, git_repo_subdir: Path
    ) -> None:
        """AC4: a tracked-but-deleted file in the spec stages its deletion."""
        pkg = git_repo_subdir / "packages" / "pkg"
        pkg.mkdir(parents=True)
        tracked = pkg / "gone.py"
        tracked.write_text("z = 3\n")
        _subdir_run(["git", "add", "-A"], git_repo_subdir)
        _subdir_run(["git", "commit", "-m", "add gone"], git_repo_subdir)

        tracked.unlink()

        result = GitCommitTool().execute(
            path=str(pkg),
            commits=[
                {"message": "chore: drop gone", "files": ["packages/pkg/gone.py"]}
            ],
        )

        assert result.success, result.error
        tree = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            cwd=git_repo_subdir,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "packages/pkg/gone.py" not in tree.stdout.splitlines()

    def test_commit_skips_gitignored_file_with_warning(
        self, git_repo_subdir: Path
    ) -> None:
        """AC5: a gitignored file in the spec is skipped, not a hard failure."""
        (git_repo_subdir / ".gitignore").write_text("ignored.py\n")
        _subdir_run(["git", "add", "-A"], git_repo_subdir)
        _subdir_run(["git", "commit", "-m", "add gitignore"], git_repo_subdir)

        (git_repo_subdir / "kept.py").write_text("k = 1\n")
        (git_repo_subdir / "ignored.py").write_text("i = 1\n")

        result = GitCommitTool().execute(
            path=str(git_repo_subdir),
            commits=[{"message": "feat: kept", "files": ["kept.py", "ignored.py"]}],
        )

        assert result.success, result.error
        committed = _committed_files_subdir(git_repo_subdir)
        assert "kept.py" in committed
        assert "ignored.py" not in committed


@pytest.fixture
def repo_with_autofix_hook(tmp_path: Path) -> Path:
    """A real git repo whose pre-commit hook rewrites the committed file once.

    The hook appends a newline to ``packages/pkg/fix_me.py`` and exits
    non-zero with the canonical 'files were modified by this hook'
    message, but only on the first invocation (guarded by a sentinel),
    so the retried commit can succeed.
    """
    _subdir_run(["git", "init"], tmp_path)
    _subdir_run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _subdir_run(["git", "config", "user.name", "Test"], tmp_path)
    _subdir_run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("init\n")
    _subdir_run(["git", "add", "-A"], tmp_path)
    _subdir_run(["git", "commit", "-m", "init"], tmp_path)

    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        "#!/bin/sh\n"
        'sentinel="$(git rev-parse --git-dir)/autofix-done"\n'
        'if [ ! -f "$sentinel" ]; then\n'
        '  touch "$sentinel"\n'
        '  printf "\\n" >> packages/pkg/fix_me.py\n'
        '  echo "files were modified by this hook"\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    hook.chmod(0o755)
    return tmp_path


@pytest.mark.integration
def test_autofix_restage_from_package_path(repo_with_autofix_hook: Path) -> None:
    """AC6: after a pre-commit autofix, re-staging from a package path works.

    GitCommitTool invoked with ``path`` at a package subdir must route the
    autofix re-stage through the subdir-aware resolver, so the retried
    commit succeeds.
    """
    repo = repo_with_autofix_hook
    pkg = repo / "packages" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "fix_me.py").write_text("v = 1\n")

    result = GitCommitTool().execute(
        path=str(pkg),
        commits=[{"message": "feat: fix_me", "files": ["packages/pkg/fix_me.py"]}],
    )

    assert result.success, result.error
    show = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "packages/pkg/fix_me.py" in show.stdout.splitlines()


class TestMidBatchFailure:
    """Commit 2/3 fails pre-commit → failure with succeeded=1, partial results."""

    @pytest.fixture()
    def three_commits(self) -> list[dict[str, Any]]:
        return [
            {"files": ["a.py"], "message": "first commit"},
            {"files": ["b.py"], "message": "second commit"},
            {"files": ["c.py"], "message": "third commit"},
        ]

    @patch(f"{MODULE}.find_git_root")
    @patch(f"{MODULE}.stage_spec_files", return_value=None)
    @patch(f"{MODULE}.author_args", return_value=[])
    @patch(f"{MODULE}.resolve_identity", return_value=None)
    @patch(f"{MODULE}.run_git")
    def test_mid_batch_precommit_failure(
        self,
        mock_run_git: MagicMock,
        _mock_identity: MagicMock,
        _mock_args: MagicMock,
        _mock_stage: MagicMock,
        mock_root: MagicMock,
        tmp_path: Path,
        three_commits: list[dict[str, Any]],
    ) -> None:
        mock_root.return_value = tmp_path
        # Staging is delegated to the (mocked) resolver. run_git now sees only
        # commit/log calls: commit1 succeeds (commit + log), commit2 fails its
        # commit. A function side-effect keeps the test robust to the exact
        # per-commit call sequence.
        commit_count = 0

        def _run_git(cmd: list[str], cwd: Any, **kw: Any) -> SimpleNamespace:
            nonlocal commit_count
            if cmd[0] == "commit":
                commit_count += 1
                if commit_count == 2:
                    return _git_result(1, stderr="pre-commit hook failed")
                return _git_result(0, stdout="[main abc1234] first commit\n")
            if cmd[0] == "log":
                return _git_result(0, stdout="abc1234abcdef1234567890\n")
            return _git_result(0)

        mock_run_git.side_effect = _run_git

        tool = GitCommitTool()
        result = tool.execute(path=str(tmp_path), commits=three_commits)

        assert result.success is False
        assert result.error is not None
        assert "Commit 2" in result.error
        assert "pre-commit failed" in result.error
        assert result.data["succeeded"] == 1
        assert len(result.data["results"]) == 1
        assert result.data["results"][0]["message"] == "first commit"
        assert result.data["results"][0]["sha"] == "abc1234"

    @patch(f"{MODULE}.find_git_root")
    @patch(f"{MODULE}.stage_spec_files", return_value=None)
    @patch(f"{MODULE}.author_args", return_value=[])
    @patch(f"{MODULE}.resolve_identity", return_value=None)
    @patch(f"{MODULE}.run_git")
    def test_mid_batch_failure_includes_failed_commit_details(
        self,
        mock_run_git: MagicMock,
        _mock_identity: MagicMock,
        _mock_args: MagicMock,
        _mock_stage: MagicMock,
        mock_root: MagicMock,
        tmp_path: Path,
        three_commits: list[dict[str, Any]],
    ) -> None:
        mock_root.return_value = tmp_path
        commit_count = 0

        def _run_git(cmd: list[str], cwd: Any, **kw: Any) -> SimpleNamespace:
            nonlocal commit_count
            if cmd[0] == "commit":
                commit_count += 1
                if commit_count == 2:
                    return _git_result(1, stderr="hook error output")
                return _git_result(0, stdout="[main aaa] first\n")
            if cmd[0] == "log":
                return _git_result(0, stdout="aaaaaaa\n")
            return _git_result(0)

        mock_run_git.side_effect = _run_git

        tool = GitCommitTool()
        result = tool.execute(path=str(tmp_path), commits=three_commits)

        failed = result.data["failed_commit"]
        assert failed["index"] == 2
        assert failed["message"] == "second commit"
        assert failed["retried"] is False
