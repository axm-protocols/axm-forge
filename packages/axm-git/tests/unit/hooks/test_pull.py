"""Tests for PullHook."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.hooks.pull import PullHook


class TestPullHook:
    """Tests for PullHook."""

    def test_pull_hook_success(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Successful pull returns HookResult.ok with pulled=True."""
        calls: list[list[str]] = []

        def fake_run_git(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.pull.run_git", fake_run_git)

        hook = PullHook()
        result = hook.execute({"working_dir": str(tmp_git_repo)})

        assert result.success
        assert result.metadata["pulled"] is True
        assert result.metadata["branch"] == "main"
        assert calls == [["pull", "origin", "main"]]

    def test_pull_hook_not_git_repo(self, tmp_path: Path) -> None:
        """Hook skips when working_dir is not a git repo."""
        hook = PullHook()
        result = hook.execute({"working_dir": str(tmp_path)})
        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "not a git repo"

    def test_pull_hook_disabled(self) -> None:
        """Hook skips when enabled=False."""
        hook = PullHook()
        result = hook.execute({"working_dir": "."}, enabled=False)
        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "git disabled"

    def test_pull_hook_failure(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pull failure returns HookResult.fail."""
        monkeypatch.setattr(
            "axm_git.hooks.pull.run_git",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 1, stdout="", stderr="fatal: couldn't find remote ref"
            ),
        )

        hook = PullHook()
        result = hook.execute({"working_dir": str(tmp_git_repo)})
        assert not result.success

    def test_pull_hook_already_up_to_date(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """'Already up to date.' is treated as success."""
        monkeypatch.setattr(
            "axm_git.hooks.pull.run_git",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 0, stdout="Already up to date.\n", stderr=""
            ),
        )

        hook = PullHook()
        result = hook.execute({"working_dir": str(tmp_git_repo)})
        assert result.success
        assert result.metadata["pulled"] is True

    def test_pull_hook_custom_branch(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Custom branch param pulls that branch instead of main."""
        calls: list[list[str]] = []

        def fake_run_git(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.pull.run_git", fake_run_git)

        hook = PullHook()
        result = hook.execute({"working_dir": str(tmp_git_repo)}, branch="develop")
        assert result.success
        assert result.metadata["branch"] == "develop"
        assert calls == [["pull", "origin", "develop"]]

    def test_pull_hook_custom_remote(
        self,
        tmp_git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Custom remote param pulls from that remote instead of origin."""
        calls: list[list[str]] = []

        def fake_run_git(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.pull.run_git", fake_run_git)

        hook = PullHook()
        result = hook.execute({"working_dir": str(tmp_git_repo)}, remote="upstream")
        assert result.success
        assert calls == [["pull", "upstream", "main"]]

    def test_pull_hook_dict_worktree_path(
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
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.pull.run_git", fake_run_git)

        hook = PullHook()
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


class TestPullHookDiscoverable:
    """Functional test for entry point discovery."""

    def test_pull_hook_discoverable(self) -> None:
        """git:pull-main entry point resolves to PullHook."""
        from importlib.metadata import entry_points

        eps = entry_points(group="axm.hooks", name="git:pull-main")
        assert len(list(eps)) == 1
        hook_cls = next(iter(eps)).load()
        assert hook_cls is PullHook
