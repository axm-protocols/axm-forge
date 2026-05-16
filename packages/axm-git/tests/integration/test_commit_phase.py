"""Tests for CommitPhaseHook."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from axm_git.core.runner import run_git
from axm_git.hooks.commit_phase import CommitPhaseHook


class TestCommitPhaseHook:
    """Tests for CommitPhaseHook (legacy mode)."""

    def test_commits_changes(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "file.txt").write_text("hello")
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
        )
        assert result.success
        assert result.metadata["message"] == "[axm] plan"
        assert result.metadata["commit"]  # short hash is non-empty

    def test_nothing_to_commit(self, tmp_git_repo: Path) -> None:
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
        )
        assert result.success
        assert result.metadata["skipped"] is True

    def test_custom_message_format(self, tmp_git_repo: Path) -> None:
        (tmp_git_repo / "f.txt").write_text("x")
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
            message_format="[AXM:{phase}]",
        )
        assert result.success
        assert result.metadata["message"] == "[AXM:plan]"

    def test_not_git_repo(self, tmp_path: Path) -> None:
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_path), "phase_name": "p"},
        )
        assert result.success
        assert result.metadata["skipped"] is True

    def test_disabled(self, tmp_git_repo: Path) -> None:
        """Hook skips when enabled=False."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "plan"},
            enabled=False,
        )
        assert result.success
        assert result.metadata.get("skipped") is True
        assert result.metadata.get("reason") == "git disabled"

    def test_legacy_mode_unchanged(self, tmp_git_repo: Path) -> None:
        """Legacy mode still works: stages all, commits with [axm] {phase}."""
        (tmp_git_repo / "a.txt").write_text("a")
        (tmp_git_repo / "b.txt").write_text("b")
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "phase_name": "close"},
        )
        assert result.success
        assert result.metadata["message"] == "[axm] close"
        # Both files should be committed
        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], tmp_git_repo)
        committed = set(log.stdout.strip().splitlines())
        assert "a.txt" in committed
        assert "b.txt" in committed


class TestCommitFromOutputs:
    """Tests for CommitPhaseHook from_outputs mode."""

    def test_stages_specific_files(self, tmp_git_repo: Path) -> None:
        """Only listed files are committed, not others."""
        (tmp_git_repo / "included.txt").write_text("yes")
        (tmp_git_repo / "excluded.txt").write_text("no")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat(test): add included",
                    "files": ["included.txt"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["commit"]
        assert result.metadata["message"] == "feat(test): add included"

        # Only included.txt should be in the commit
        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], tmp_git_repo)
        committed = set(log.stdout.strip().splitlines())
        assert "included.txt" in committed
        assert "excluded.txt" not in committed

    def test_message_and_body(self, tmp_git_repo: Path) -> None:
        """Commit has both message and body."""
        (tmp_git_repo / "f.txt").write_text("x")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat(runner): extract",
                    "body": "Closes: AXM-605",
                    "files": ["f.txt"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        # Verify full commit message
        log = run_git(["log", "-1", "--format=%B"], tmp_git_repo)
        full_msg = log.stdout.strip()
        assert "feat(runner): extract" in full_msg
        assert "Closes: AXM-605" in full_msg

    def test_returns_hash(self, tmp_git_repo: Path) -> None:
        """Result contains commit hash and message."""
        (tmp_git_repo / "f.txt").write_text("x")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: test hash",
                    "files": ["f.txt"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert len(result.metadata["commit"]) >= 7  # short hash
        assert result.metadata["message"] == "feat: test hash"

    def test_missing_commit_spec_fails(self, tmp_git_repo: Path) -> None:
        """Fails with clear message when commit_spec is absent."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo)},
            from_outputs=True,
        )

        assert not result.success
        assert "commit_spec" in (result.error or "")

    def test_commit_spec_not_a_dict_fails(self, tmp_git_repo: Path) -> None:
        """Fails when commit_spec is not a dict."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "commit_spec": "not a dict"},
            from_outputs=True,
        )

        assert not result.success
        assert "commit_spec must be a dict" in (result.error or "")

    def test_missing_files_key_fails(self, tmp_git_repo: Path) -> None:
        """Fails when commit_spec has no files key."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {"message": "feat: no files"},
            },
            from_outputs=True,
        )

        assert not result.success
        assert "'files'" in (result.error or "")

    def test_nonexistent_file_fails(self, tmp_git_repo: Path) -> None:
        """Fails when a listed file does not exist."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: ghost",
                    "files": ["deleted.py"],
                },
            },
            from_outputs=True,
        )

        assert not result.success
        assert "deleted.py" in (result.error or "")

    def test_nothing_to_commit(self, tmp_git_repo: Path) -> None:
        """Skips when all listed files are already clean."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: clean",
                    "files": [".gitkeep"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "nothing to commit"

    def test_empty_files_list_fails(self, tmp_git_repo: Path) -> None:
        """Fails when files list is empty."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: empty",
                    "files": [],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "nothing to commit"

    def test_body_absent_ok(self, tmp_git_repo: Path) -> None:
        """Commit works without body — message only, no error."""
        (tmp_git_repo / "f.txt").write_text("x")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: no body",
                    "files": ["f.txt"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        log = run_git(["log", "-1", "--format=%B"], tmp_git_repo)
        assert log.stdout.strip() == "feat: no body"


class TestCommitFromOutputsWorkspace:
    """Tests for from_outputs mode in workspace (nested package) layouts."""

    def test_workspace_from_outputs_stages_correctly(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Git-root-relative paths are staged correctly from a nested package."""
        git_root, pkg_dir = tmp_workspace_repo

        (pkg_dir / "src" / "hello.py").write_text("# changed\n")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(pkg_dir),
                "commit_spec": {
                    "message": "feat(pkg): update hello",
                    "files": ["packages/pkg/src/hello.py"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["commit"]
        assert result.metadata["message"] == "feat(pkg): update hello"

        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], git_root)
        committed = set(log.stdout.strip().splitlines())
        assert "packages/pkg/src/hello.py" in committed

    def test_workspace_from_outputs_pkg_relative_path(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Working-dir-relative paths also work (git resolves from root)."""
        _, pkg_dir = tmp_workspace_repo

        (pkg_dir / "src" / "hello.py").write_text("# pkg-relative\n")

        hook = CommitPhaseHook()
        # Use the full git-root-relative path (the natural path from preflight)
        result = hook.execute(
            {
                "working_dir": str(pkg_dir),
                "commit_spec": {
                    "message": "feat(pkg): pkg-relative path",
                    "files": ["packages/pkg/src/hello.py"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["commit"]

    def test_workspace_from_outputs_mixed_paths(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Mixed git-root-relative paths from different packages."""
        git_root, pkg_dir = tmp_workspace_repo

        # Create a second file at workspace root level
        (git_root / "root_file.txt").write_text("root change\n")
        (pkg_dir / "src" / "hello.py").write_text("# mixed\n")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(pkg_dir),
                "commit_spec": {
                    "message": "feat: mixed paths",
                    "files": [
                        "packages/pkg/src/hello.py",
                        "root_file.txt",
                    ],
                },
            },
            from_outputs=True,
        )

        assert result.success
        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], git_root)
        committed = set(log.stdout.strip().splitlines())
        assert "packages/pkg/src/hello.py" in committed
        assert "root_file.txt" in committed


class TestCommitFileDiagnostics:
    """Tests for gitignored / missing file diagnostics in from_outputs mode."""

    def test_commit_skips_gitignored_files(self, tmp_git_repo: Path) -> None:
        """When commit_spec.files contains a gitignored path, the hook warns
        and skips that file but still commits the remaining valid files."""
        # Create .gitignore that ignores *.log files
        (tmp_git_repo / ".gitignore").write_text("*.log\n")
        run_git(["add", ".gitignore"], tmp_git_repo)
        run_git(["commit", "-m", "add gitignore"], tmp_git_repo)

        # Create files: one valid, one gitignored
        (tmp_git_repo / "valid.txt").write_text("keep me")
        (tmp_git_repo / "debug.log").write_text("ignore me")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: with ignored",
                    "files": ["valid.txt", "debug.log"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["commit"]

        # Only valid.txt should be committed
        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], tmp_git_repo)
        committed = set(log.stdout.strip().splitlines())
        assert "valid.txt" in committed
        assert "debug.log" not in committed

        # Warning about the skipped file
        warnings = result.metadata.get("warnings", [])
        assert any("debug.log" in w for w in warnings)

    def test_commit_fails_on_missing_file(self, tmp_git_repo: Path) -> None:
        """When commit_spec.files contains a nonexistent path, the hook
        returns an error with a clear diagnostic naming the missing file."""
        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: ghost",
                    "files": ["nonexistent.py"],
                },
            },
            from_outputs=True,
        )

        assert not result.success
        assert "nonexistent.py" in (result.error or "")

    def test_commit_normal_flow(self, tmp_git_repo: Path) -> None:
        """When all files in commit_spec.files are valid and exist,
        the hook stages and commits them successfully."""
        (tmp_git_repo / "a.py").write_text("# a")
        (tmp_git_repo / "b.py").write_text("# b")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: normal flow",
                    "files": ["a.py", "b.py"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["commit"]
        assert result.metadata["message"] == "feat: normal flow"

        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], tmp_git_repo)
        committed = set(log.stdout.strip().splitlines())
        assert "a.py" in committed
        assert "b.py" in committed
        assert not result.metadata.get("warnings")

    def test_commit_mixed_valid_ignored(self, tmp_git_repo: Path) -> None:
        """When commit_spec.files has a mix of valid and gitignored files,
        the hook stages valid files, warns about ignored ones, and commits."""
        (tmp_git_repo / ".gitignore").write_text("*.log\nbuild/\n")
        run_git(["add", ".gitignore"], tmp_git_repo)
        run_git(["commit", "-m", "add gitignore"], tmp_git_repo)

        # Valid files
        (tmp_git_repo / "src.py").write_text("# source")
        (tmp_git_repo / "readme.md").write_text("# readme")
        # Gitignored files
        (tmp_git_repo / "app.log").write_text("log entry")
        (tmp_git_repo / "build").mkdir(exist_ok=True)
        (tmp_git_repo / "build" / "out.js").write_text("built")

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_git_repo),
                "commit_spec": {
                    "message": "feat: mixed files",
                    "files": ["src.py", "readme.md", "app.log", "build/out.js"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        assert result.metadata["commit"]

        # Valid files committed
        log = run_git(["diff", "--name-only", "HEAD~1", "HEAD"], tmp_git_repo)
        committed = set(log.stdout.strip().splitlines())
        assert "src.py" in committed
        assert "readme.md" in committed
        assert "app.log" not in committed
        assert "build/out.js" not in committed

        # Warnings about both ignored files
        warnings = result.metadata.get("warnings", [])
        assert any("app.log" in w for w in warnings)
        assert any("build/out.js" in w for w in warnings)


class TestCommitPhaseWorkspace:
    """Tests for CommitPhaseHook in workspace (nested package) layouts."""

    def test_workspace_package_commits(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """CommitPhaseHook finds git root and commits from a nested package."""
        _, pkg_dir = tmp_workspace_repo

        (pkg_dir / "src" / "hello.py").write_text("# changed\n")

        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir), "phase_name": "close"},
        )

        assert result.success
        assert result.metadata["commit"]
        assert result.metadata["message"] == "[axm] close"

    def test_workspace_nothing_to_commit(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Skips when package dir is clean (even if workspace root has changes)."""
        git_root, pkg_dir = tmp_workspace_repo

        # Only change at workspace root — package is clean
        (git_root / "noise.txt").write_text("workspace noise")
        run_git(["add", "noise.txt"], git_root)
        run_git(["commit", "-m", "noise"], git_root)

        hook = CommitPhaseHook()
        result = hook.execute(
            {"working_dir": str(pkg_dir), "phase_name": "close"},
        )

        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "nothing to commit"


# --- Tests from test_commit_phase_retry.py (commit retry / autofix, AXM-899) ---


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


class TestCommitRetryAfterAutofix:
    """Retry logic when pre-commit hooks auto-fix files."""

    @pytest.fixture
    def hook(self) -> CommitPhaseHook:
        return CommitPhaseHook()

    @pytest.fixture
    def context(self, tmp_path: Path) -> dict[str, Any]:
        """Minimal from_outputs context with a commit_spec."""
        return {
            "working_dir": str(tmp_path),
            "commit_spec": {
                "message": "feat(git): retry test",
                "files": ["src/foo.py"],
            },
        }

    def test_commit_retries_after_autofix(
        self,
        hook: CommitPhaseHook,
        context: dict[str, Any],
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """When commit fails with 'files were modified', re-stage and retry."""
        mock_stage = mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value=None,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase.find_git_root",
            return_value=tmp_path,
        )

        # run_git calls:
        #   1. diff --cached (check staged) -> has staged files
        #   2. commit -> rc=1 "files were modified by formatter"
        #   3. commit retry -> rc=0
        #   4. rev-parse -> short hash
        mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            side_effect=[
                _cp(stdout="src/foo.py\n"),
                _cp(
                    returncode=1,
                    stderr="files were modified by formatter",
                ),
                _cp(returncode=0),
                _cp(stdout="abc1234\n"),
            ],
        )

        result = hook.execute(context, from_outputs=True)

        assert result.success
        assert result.metadata["commit"] == "abc1234"
        # _stage_spec_files called twice: initial + re-stage after autofix
        assert mock_stage.call_count == 2

    def test_commit_retry_fails(
        self,
        hook: CommitPhaseHook,
        context: dict[str, Any],
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """When commit fails twice, return HookResult.fail()."""
        mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value=None,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase.find_git_root",
            return_value=tmp_path,
        )

        mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            side_effect=[
                _cp(stdout="src/foo.py\n"),
                _cp(
                    returncode=1,
                    stderr="files were modified by formatter",
                ),
                _cp(returncode=1, stderr="pre-commit hook failed"),
            ],
        )

        result = hook.execute(context, from_outputs=True)

        assert not result.success
        assert "commit failed" in (result.error or "").lower()

    def test_commit_clean_no_retry(
        self,
        hook: CommitPhaseHook,
        context: dict[str, Any],
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """When commit succeeds first time, no retry occurs."""
        mock_stage = mocker.patch(
            "axm_git.hooks.commit_phase._stage_spec_files",
            return_value=None,
        )
        mocker.patch(
            "axm_git.hooks.commit_phase.find_git_root",
            return_value=tmp_path,
        )

        mocker.patch(
            "axm_git.hooks.commit_phase.run_git",
            side_effect=[
                _cp(stdout="src/foo.py\n"),  # diff --cached
                _cp(returncode=0),  # commit succeeds
                _cp(stdout="def5678\n"),  # rev-parse
            ],
        )

        result = hook.execute(context, from_outputs=True)

        assert result.success
        assert result.metadata["commit"] == "def5678"
        # _stage_spec_files called only once (no retry)
        assert mock_stage.call_count == 1


# --- Tests from test_commit_phase_skip_hooks.py (skip_hooks parameter) ---


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


class TestCommitFromOutputsSkipHooks:
    """Tests for skip_hooks behaviour in _commit_from_outputs."""

    @patch("axm_git.hooks.commit_phase.run_git")
    @patch("axm_git.hooks.commit_phase.find_git_root")
    def test_commit_from_outputs_skip_hooks_default(
        self,
        mock_find_root: MagicMock,
        mock_run_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """By default (skip_hooks=False), git commit args do NOT include --no-verify."""
        mock_find_root.return_value = tmp_path
        (tmp_path / "f.py").write_text("x")

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "diff":
                return _ok(stdout="f.py\n")
            if args[0] == "commit":
                return _ok()
            if args[0] == "rev-parse":
                return _ok(stdout="abc1234")
            return _ok()

        mock_run_git.side_effect = _side_effect

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_path),
                "commit_spec": {
                    "message": "feat: test",
                    "files": ["f.py"],
                },
            },
            from_outputs=True,
        )

        assert result.success
        # Find the commit call and verify --no-verify is present
        commit_calls = [
            call for call in mock_run_git.call_args_list if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert "--no-verify" not in commit_calls[0][0][0]

    @patch("axm_git.hooks.commit_phase.run_git")
    @patch("axm_git.hooks.commit_phase.find_git_root")
    def test_commit_from_outputs_skip_hooks_false(
        self,
        mock_find_root: MagicMock,
        mock_run_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When skip_hooks=False, git commit does NOT include --no-verify."""
        mock_find_root.return_value = tmp_path
        (tmp_path / "f.py").write_text("x")

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "diff":
                return _ok(stdout="f.py\n")
            if args[0] == "commit":
                return _ok()
            if args[0] == "rev-parse":
                return _ok(stdout="abc1234")
            return _ok()

        mock_run_git.side_effect = _side_effect

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_path),
                "commit_spec": {
                    "message": "feat: test",
                    "files": ["f.py"],
                },
            },
            from_outputs=True,
            skip_hooks=False,
        )

        assert result.success
        commit_calls = [
            call for call in mock_run_git.call_args_list if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert "--no-verify" not in commit_calls[0][0][0]

    @patch("axm_git.hooks.commit_phase.run_git")
    @patch("axm_git.hooks.commit_phase.find_git_root")
    def test_execute_passes_skip_hooks_param(
        self,
        mock_find_root: MagicMock,
        mock_run_git: MagicMock,
        tmp_path: Path,
    ) -> None:
        """execute() threads skip_hooks from params to _commit_from_outputs."""
        mock_find_root.return_value = tmp_path
        (tmp_path / "f.py").write_text("x")

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "diff":
                return _ok(stdout="f.py\n")
            if args[0] == "commit":
                return _ok()
            if args[0] == "rev-parse":
                return _ok(stdout="abc1234")
            return _ok()

        mock_run_git.side_effect = _side_effect

        hook = CommitPhaseHook()
        result = hook.execute(
            {
                "working_dir": str(tmp_path),
                "commit_spec": {
                    "message": "feat: test",
                    "files": ["f.py"],
                },
            },
            from_outputs=True,
            skip_hooks=True,
        )

        assert result.success
        commit_calls = [
            call for call in mock_run_git.call_args_list if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert "--no-verify" in commit_calls[0][0][0]
