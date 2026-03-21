"""Tests for AwaitMergeHook."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.hooks.await_merge import AwaitMergeHook


class TestAwaitMergeHook:
    """Tests for AwaitMergeHook."""

    def test_await_merge_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PR merges on the 2nd poll."""
        poll_count = 0

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            nonlocal poll_count
            poll_count += 1
            state = "OPEN" if poll_count == 1 else "MERGED"
            return subprocess.CompletedProcess(
                args, 0, stdout=f'{{"state":"{state}"}}', stderr=""
            )

        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.await_merge.run_gh", fake_run_gh)
        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", lambda _: None)

        hook = AwaitMergeHook()
        result = hook.execute(
            {"working_dir": ".", "pr_number": "42"},
            interval=1,
            timeout=10,
        )
        assert result.success
        assert result.metadata["merged"] is True
        assert poll_count == 2

    def test_await_merge_timeout(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Always OPEN → timeout."""
        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr(
            "axm_git.hooks.await_merge.run_gh",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 0, stdout='{"state":"OPEN"}', stderr=""
            ),
        )
        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", lambda _: None)

        hook = AwaitMergeHook()
        result = hook.execute(
            {"working_dir": ".", "pr_number": "42"},
            interval=1,
            timeout=3,
        )
        assert not result.success

    def test_await_merge_poll_interval(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify sleep is called with the correct interval."""
        sleep_values: list[object] = []

        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr(
            "axm_git.hooks.await_merge.run_gh",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 0, stdout='{"state":"MERGED"}', stderr=""
            ),
        )

        def fake_sleep(seconds: object) -> None:
            sleep_values.append(seconds)

        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", fake_sleep)

        hook = AwaitMergeHook()
        hook.execute(
            {"working_dir": ".", "pr_number": "1"},
            interval=30,
            timeout=600,
        )
        # Merged on first poll, no sleep needed
        assert len(sleep_values) == 0

    def test_await_merge_closed_without_merge(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PR closed without merge returns fail."""
        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr(
            "axm_git.hooks.await_merge.run_gh",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 0, stdout='{"state":"CLOSED"}', stderr=""
            ),
        )
        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", lambda _: None)

        hook = AwaitMergeHook()
        result = hook.execute(
            {"working_dir": ".", "pr_number": "42"},
            interval=1,
            timeout=10,
        )
        assert not result.success
        assert result.error is not None
        assert "closed without merging" in result.error

    def test_await_merge_no_pr_ref(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing pr_number and pr_url returns fail."""
        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)

        hook = AwaitMergeHook()
        result = hook.execute({"working_dir": "."})
        assert not result.success
        assert result.error is not None
        assert "no pr_number or pr_url" in result.error

    def test_await_merge_skip_no_gh(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Hook skips when gh is not available."""
        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: False)

        hook = AwaitMergeHook()
        result = hook.execute({"working_dir": ".", "pr_number": "42"})
        assert result.success
        assert result.metadata["skipped"] is True

    def test_await_merge_disabled(self) -> None:
        """Hook skips when enabled=False."""
        hook = AwaitMergeHook()
        result = hook.execute({"working_dir": "."}, enabled=False)
        assert result.success
        assert result.metadata["skipped"] is True

    def test_await_merge_dict_worktree_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Dict worktree_path in context is unwrapped without TypeError."""
        captured_cwd: list[Path] = []

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            captured_cwd.append(cwd)
            return subprocess.CompletedProcess(
                args, 0, stdout='{"state":"MERGED"}', stderr=""
            )

        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.await_merge.run_gh", fake_run_gh)
        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", lambda _: None)

        hook = AwaitMergeHook()
        result = hook.execute(
            {
                "worktree_path": {
                    "worktree_path": "/tmp/wt",
                    "branch": "feat/x",
                },
                "pr_number": "42",
            },
            interval=1,
            timeout=10,
        )
        assert result.success
        assert captured_cwd[0] == Path("/tmp/wt")

    def test_pr_ref_from_params_pr_url(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """pr_url passed as param is used (not only context)."""
        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr(
            "axm_git.hooks.await_merge.run_gh",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 0, stdout='{"state":"MERGED"}', stderr=""
            ),
        )
        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", lambda _: None)

        hook = AwaitMergeHook()
        result = hook.execute(
            {"working_dir": "."},
            pr_url="https://github.com/org/repo/pull/99",
            interval=1,
            timeout=10,
        )
        assert result.success
        assert result.metadata["merged"] is True

    def test_pr_ref_from_params_pr_number(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """pr_number passed as param is used."""
        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr(
            "axm_git.hooks.await_merge.run_gh",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 0, stdout='{"state":"MERGED"}', stderr=""
            ),
        )
        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", lambda _: None)

        hook = AwaitMergeHook()
        result = hook.execute(
            {"working_dir": "."},
            pr_number="42",
            interval=1,
            timeout=10,
        )
        assert result.success
        assert result.metadata["merged"] is True

    def test_params_pr_ref_overrides_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Params pr_url wins over context pr_url."""
        captured_args: list[list[str]] = []

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            captured_args.append(args)
            return subprocess.CompletedProcess(
                args, 0, stdout='{"state":"MERGED"}', stderr=""
            )

        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.await_merge.run_gh", fake_run_gh)
        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", lambda _: None)

        hook = AwaitMergeHook()
        result = hook.execute(
            {"working_dir": ".", "pr_url": "context-url"},
            pr_url="params-url",
            interval=1,
            timeout=10,
        )
        assert result.success
        # The gh command should use the params value, not context
        assert any("params-url" in str(a) for a in captured_args)

    def test_await_merge_network_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """gh command fails during poll → fail with descriptive message."""
        monkeypatch.setattr("axm_git.hooks.await_merge.gh_available", lambda: True)
        monkeypatch.setattr(
            "axm_git.hooks.await_merge.run_gh",
            lambda args, cwd, **kw: subprocess.CompletedProcess(
                args, 1, stdout="", stderr="network error"
            ),
        )
        monkeypatch.setattr("axm_git.hooks.await_merge.time.sleep", lambda _: None)

        hook = AwaitMergeHook()
        result = hook.execute(
            {"working_dir": ".", "pr_number": "42"},
            interval=1,
            timeout=5,
        )
        assert not result.success
        assert result.error is not None
        assert "failed to query" in result.error
