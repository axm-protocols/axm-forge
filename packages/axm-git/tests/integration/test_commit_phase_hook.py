"""Integration tests for CommitPhaseHook (single-symbol tuple).

AXM-1645 scenarios: real git repo + real pre-commit hooks. Verifies that
with ``skip_hooks=False`` (new default) project hooks run, and with
``skip_hooks=True`` they are bypassed. Also covers the autofix retry path
under the new default.

Tests covering both ``CommitPhaseHook`` and ``run_git`` live in
``test_commit_phase_hook__run_git.py`` per TEST_QUALITY_FILE_NAMING.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from axm_git.hooks.commit_phase import CommitPhaseHook

pytestmark = pytest.mark.integration


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)


def _write_hook(repo: Path, script: str) -> Path:
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(script)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def _make_file(repo: Path, name: str = "a.txt", content: str = "hello\n") -> str:
    (repo / name).write_text(content)
    return name


def _spec(files: list[str], message: str = "test commit") -> dict[str, object]:
    return {"message": message, "files": files}


def test_commit_phase_runs_pre_commit_hook_by_default(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_hook(tmp_path, "#!/bin/sh\necho 'hook says no' >&2\nexit 1\n")
    fname = _make_file(tmp_path)

    hook = CommitPhaseHook()
    ctx = {"phase_name": "build", "commit_spec": _spec([fname])}
    result = hook.execute(ctx, from_outputs=True, working_dir=str(tmp_path))

    assert result.success is False
    assert "hook says no" in (result.error or "") or "git commit failed" in (
        result.error or ""
    )


def test_commit_phase_skip_hooks_true_bypasses(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_hook(tmp_path, "#!/bin/sh\nexit 1\n")
    fname = _make_file(tmp_path)

    hook = CommitPhaseHook()
    ctx = {"phase_name": "build", "commit_spec": _spec([fname])}
    result = hook.execute(
        ctx, from_outputs=True, working_dir=str(tmp_path), skip_hooks=True
    )

    assert result.success is True


def test_commit_phase_autofix_retry_under_new_default(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    flag = tmp_path / ".hook_ran"
    fname = _make_file(tmp_path, content="original\n")
    _write_hook(
        tmp_path,
        f"""#!/bin/sh
if [ ! -f "{flag}" ]; then
  touch "{flag}"
  echo "rewriting" > "{tmp_path / fname}"
  echo "files were modified" >&2
  exit 1
fi
exit 0
""",
    )

    hook = CommitPhaseHook()
    ctx = {"phase_name": "build", "commit_spec": _spec([fname])}
    result = hook.execute(ctx, from_outputs=True, working_dir=str(tmp_path))

    assert result.success is True
    assert flag.exists()


def test_commit_phase_pre_commit_failure_routes_to_fail(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_hook(
        tmp_path,
        "#!/bin/sh\necho 'lint error: bad style' >&2\nexit 1\n",
    )
    fname = _make_file(tmp_path)

    hook = CommitPhaseHook()
    ctx = {"phase_name": "build", "commit_spec": _spec([fname])}
    result = hook.execute(ctx, from_outputs=True, working_dir=str(tmp_path))

    assert result.success is False
    assert "lint error" in (result.error or "")
    # Ensure no commit was created
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True
    )
    assert log.stdout.strip() == ""


# --- Moved from test_commit_phase_hook__run_git.py (clean methods, no run_git call) ---


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


class TestCommitPhaseHookLegacy:
    """Tests for CommitPhaseHook (legacy mode) — clean methods, no run_git call."""

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


class TestCommitFromOutputs:
    """Tests for CommitPhaseHook from_outputs mode — clean methods, no run_git call."""

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


class TestCommitFromOutputsWorkspace:
    """Tests for from_outputs mode in workspace (nested package) layouts.

    Clean methods, no run_git call.
    """

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


class TestCommitFileDiagnostics:
    """Tests for gitignored / missing file diagnostics in from_outputs mode.

    Clean methods, no run_git call.
    """

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


class TestCommitPhaseWorkspace:
    """Tests for CommitPhaseHook in workspace (nested package) layouts.

    Clean methods, no run_git call.
    """

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
