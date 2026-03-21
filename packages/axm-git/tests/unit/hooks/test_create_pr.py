"""Tests for CreatePRHook."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.hooks.create_pr import CreatePRHook, _format_pr_title


class TestFormatPRTitle:
    """Tests for _format_pr_title helper."""

    def test_appends_ticket_id(self) -> None:
        title = _format_pr_title(
            {"message": "feat(git): add PR hooks"},
            "AXM-42",
        )
        assert title == "feat(git): add PR hooks [AXM-42]"

    def test_no_duplicate_ticket_id(self) -> None:
        title = _format_pr_title(
            {"message": "feat(git): add PR hooks [AXM-42]"},
            "AXM-42",
        )
        assert title == "feat(git): add PR hooks [AXM-42]"

    def test_empty_ticket_id(self) -> None:
        title = _format_pr_title(
            {"message": "feat(git): add PR hooks"},
            "",
        )
        assert title == "feat(git): add PR hooks"


class TestCreatePRHook:
    """Tests for CreatePRHook."""

    def test_create_pr_calls_gh(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify gh pr create and gh pr merge --auto --squash are called."""
        calls: list[list[str]] = []

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            calls.append(args)
            if args[1] == "create":
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="https://github.com/org/repo/pull/99\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.create_pr.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.create_pr.run_gh", fake_run_gh)

        hook = CreatePRHook()
        result = hook.execute(
            {
                "working_dir": ".",
                "commit_spec": {"message": "feat(git): hooks", "body": "PR body"},
                "ticket_id": "AXM-42",
            },
        )
        assert result.success
        assert result.metadata["pr_url"] == "https://github.com/org/repo/pull/99"
        assert result.metadata["pr_number"] == "99"
        assert result.metadata["auto_merge"] is True

        # Verify both calls
        assert calls[0][:3] == ["pr", "create", "--title"]
        assert calls[1] == ["pr", "merge", "99", "--auto", "--squash"]

    def test_create_pr_title_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PR title matches conventional commit format with ticket ID."""
        captured_title: list[str] = []

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            if args[1] == "create":
                title_idx = args.index("--title") + 1
                captured_title.append(args[title_idx])
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="https://github.com/org/repo/pull/1\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.create_pr.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.create_pr.run_gh", fake_run_gh)

        hook = CreatePRHook()
        hook.execute(
            {
                "working_dir": ".",
                "commit_spec": {"message": "feat(git): add PR hooks"},
                "ticket_id": "AXM-42",
            },
        )
        assert captured_title[0] == "feat(git): add PR hooks [AXM-42]"

    def test_create_pr_skip_no_gh(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Hook skips when gh is not available."""
        monkeypatch.setattr("axm_git.hooks.create_pr.gh_available", lambda: False)

        hook = CreatePRHook()
        result = hook.execute({"working_dir": "."})
        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "gh not available"

    def test_create_pr_already_exists(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When PR already exists, recover the existing PR URL."""

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            if args[1] == "create":
                return subprocess.CompletedProcess(
                    args, 1, stdout="", stderr="a]pull request already exists"
                )
            if args[1] == "view":
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout='{"url":"https://github.com/org/repo/pull/50","number":50}',
                    stderr="",
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.create_pr.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.create_pr.run_gh", fake_run_gh)

        hook = CreatePRHook()
        result = hook.execute(
            {
                "working_dir": ".",
                "commit_spec": {"message": "feat: x"},
                "ticket_id": "AXM-1",
            },
        )
        assert result.success
        assert result.metadata["pr_url"] == "https://github.com/org/repo/pull/50"
        assert result.metadata["already_existed"] is True

    def test_create_pr_disabled(self) -> None:
        """Hook skips when enabled=False."""
        hook = CreatePRHook()
        result = hook.execute({"working_dir": "."}, enabled=False)
        assert result.success
        assert result.metadata["skipped"] is True

    def test_create_pr_auto_merge_failure_non_fatal(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PR created but auto-merge fails is still a success."""

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            if args[1] == "create":
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="https://github.com/org/repo/pull/10\n",
                    stderr="",
                )
            if args[1] == "merge":
                return subprocess.CompletedProcess(
                    args, 1, stdout="", stderr="auto-merge not allowed"
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.create_pr.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.create_pr.run_gh", fake_run_gh)

        hook = CreatePRHook()
        result = hook.execute(
            {
                "working_dir": ".",
                "commit_spec": {"message": "feat: x"},
                "ticket_id": "",
            },
        )
        assert result.success
        assert result.metadata["auto_merge"] is False
        assert result.metadata["pr_url"] == "https://github.com/org/repo/pull/10"


class TestCreatePRHookParamsOverride:
    """Regression tests: params take precedence over context (AXM-665)."""

    def test_commit_spec_from_params(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """commit_spec passed as param overrides context value."""
        captured_title: list[str] = []

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            if args[1] == "create":
                title_idx = args.index("--title") + 1
                captured_title.append(args[title_idx])
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="https://github.com/org/repo/pull/1\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.create_pr.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.create_pr.run_gh", fake_run_gh)

        hook = CreatePRHook()
        result = hook.execute(
            {"commit_spec": {"message": "wrong"}, "ticket_id": "AXM-1"},
            commit_spec={"message": "feat(git): from params"},
        )
        assert result.success
        assert captured_title[0] == "feat(git): from params [AXM-1]"

    def test_ticket_id_from_params(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ticket_id passed as param overrides context value."""
        captured_title: list[str] = []

        def fake_run_gh(
            args: list[str], cwd: Path, **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            if args[1] == "create":
                title_idx = args.index("--title") + 1
                captured_title.append(args[title_idx])
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="https://github.com/org/repo/pull/2\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        monkeypatch.setattr("axm_git.hooks.create_pr.gh_available", lambda: True)
        monkeypatch.setattr("axm_git.hooks.create_pr.run_gh", fake_run_gh)

        hook = CreatePRHook()
        result = hook.execute(
            {"ticket_id": "AXM-OLD", "commit_spec": {"message": "feat: x"}},
            ticket_id="AXM-NEW",
        )
        assert result.success
        assert captured_title[0] == "feat: x [AXM-NEW]"
