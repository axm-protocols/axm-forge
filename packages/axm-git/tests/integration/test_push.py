"""Tests for PushHook."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.hooks.push import PushHook


class TestPushHook:
    """Tests for PushHook."""

    def test_push_hook_pushes_branch(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mock run_git and verify push is called with correct args."""
        calls: list[list[str]] = []

        def fake_run_git(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if args[0] == "rev-parse":
                return subprocess.CompletedProcess(
                    args, 0, stdout="feat/AXM-42-slug\n", stderr=""
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.push.run_git", fake_run_git)

        hook = PushHook()
        hook.execute({"working_dir": str(tmp_git_repo)})

        push_calls = [c for c in calls if c[0] == "push"]
        assert len(push_calls) == 1
        assert push_calls[0] == ["push", "-u", "origin", "feat/AXM-42-slug"]

    def test_push_hook_returns_ok(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Successful push returns HookResult.ok with pushed=True."""
        monkeypatch.setattr(
            "axm_git.hooks.push.run_git",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args,
                0,
                stdout="feat/my-branch\n" if args[0] == "rev-parse" else "",
                stderr="",
            ),
        )

        hook = PushHook()
        result = hook.execute({"working_dir": str(tmp_git_repo)})
        assert result.success
        assert result.metadata["pushed"] is True

    def test_push_hook_uses_context_branch(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When context has 'branch', use it directly without rev-parse."""
        calls: list[list[str]] = []

        def fake_run_git(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.push.run_git", fake_run_git)

        hook = PushHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "branch": "feat/AXM-99-test"},
        )
        assert result.success
        assert result.metadata["branch"] == "feat/AXM-99-test"
        # Should NOT call rev-parse
        assert not any(c[0] == "rev-parse" for c in calls)

    def test_push_hook_fail_on_error(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Push failure returns HookResult.fail."""
        monkeypatch.setattr(
            "axm_git.hooks.push.run_git",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 1, stdout="", stderr="remote rejected"
            ),
        )

        hook = PushHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "branch": "feat/x"},
        )
        assert not result.success

    def test_push_hook_everything_up_to_date(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """'Everything up-to-date' is treated as success."""
        monkeypatch.setattr(
            "axm_git.hooks.push.run_git",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args,
                1,
                stdout="",
                stderr="Everything up-to-date",
            ),
        )

        hook = PushHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo), "branch": "feat/x"},
        )
        assert result.success
        assert result.metadata["pushed"] is True

    def test_push_hook_disabled(self) -> None:
        """Hook skips when enabled=False."""
        hook = PushHook()
        result = hook.execute({"working_dir": "."}, enabled=False)
        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "git disabled"

    def test_push_hook_not_git_repo(self, tmp_path: Path) -> None:
        """Hook skips when working_dir is not a git repo."""
        hook = PushHook()
        result = hook.execute({"working_dir": str(tmp_path)})
        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "not a git repo"

    def test_subdirectory_of_git_repo(
        self,
        tmp_workspace_repo: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Push succeeds when working_dir is a subdirectory of a git repo."""
        git_root, pkg_dir = tmp_workspace_repo
        captured_cwd: list[Path] = []

        def fake_run_git(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            captured_cwd.append(cwd)
            if args[0] == "rev-parse":
                return subprocess.CompletedProcess(args, 0, stdout="main\n", stderr="")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.push.run_git", fake_run_git)

        hook = PushHook()
        result = hook.execute({"working_dir": str(pkg_dir)})
        assert result.success
        assert result.metadata["pushed"] is True
        # run_git should receive git_root, not the package subdir
        assert all(cwd == git_root for cwd in captured_cwd)

    def test_push_dict_worktree_path(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Dict worktree_path in context is unwrapped without TypeError."""
        captured_cwd: list[Path] = []

        def fake_run_git(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            captured_cwd.append(cwd)
            if args[0] == "rev-parse":
                return subprocess.CompletedProcess(
                    args, 0, stdout="feat/x\n", stderr=""
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.push.run_git", fake_run_git)

        hook = PushHook()
        result = hook.execute(
            {
                "worktree_path": {
                    "worktree_path": str(tmp_git_repo),
                    "branch": "feat/x",
                },
            },
        )
        assert result.success
        assert captured_cwd[0] == Path(tmp_git_repo)
