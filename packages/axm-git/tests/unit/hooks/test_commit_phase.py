"""Unit tests for axm_git.hooks.commit_phase (no real I/O)."""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_git.hooks.commit_phase import CommitPhaseHook, _build_commit_cmd


def _ok(stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )


class TestBuildCommitCmd:
    """Unit-scope tests for _build_commit_cmd (no I/O)."""

    def test_build_commit_cmd_no_verify_omitted_when_skip_hooks_false(self) -> None:
        cmd = _build_commit_cmd("msg", None, skip_hooks=False)
        assert "--no-verify" not in cmd

    def test_build_commit_cmd_no_verify_present_when_skip_hooks_true(self) -> None:
        cmd = _build_commit_cmd("msg", None, skip_hooks=True)
        assert "--no-verify" in cmd

    def test_commit_phase_default_skip_hooks_is_false(self) -> None:
        sig = inspect.signature(CommitPhaseHook._commit_from_outputs)
        assert sig.parameters["skip_hooks"].default is False


class TestCommitToolNoSkip:
    """Verify CommitTool (MCP) does NOT use --no-verify."""

    @patch("axm_git.tools.commit.run_git")
    def test_commit_tool_no_skip(self, mock_git: MagicMock) -> None:
        """CommitTool.execute does NOT include --no-verify."""
        from axm_git.tools.commit import GitCommitTool

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "add":
                return _ok()
            if args[0] == "commit":
                return _ok()
            if args[0] == "log":
                return _ok("abc1234")
            return _ok()

        mock_git.side_effect = _side_effect
        result = GitCommitTool().execute(
            path="/tmp/test",
            commits=[{"files": ["src/foo.py"], "message": "fix: bug"}],
        )

        assert result.success
        commit_calls = [
            call for call in mock_git.call_args_list if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert "--no-verify" not in commit_calls[0][0][0]


# ---------------------------------------------------------------------------
# Identity-aware commit (formerly tests/unit/test_commit_phase_identity.py)
# ---------------------------------------------------------------------------


def test_build_commit_cmd_with_author() -> None:
    """_build_commit_cmd includes --author flag when author is provided."""
    cmd = _build_commit_cmd(
        "msg", None, skip_hooks=True, author="Axiom <axiom@axm-protocol.io>"
    )
    assert "--author=Axiom <axiom@axm-protocol.io>" in cmd


def test_build_commit_cmd_no_author() -> None:
    """_build_commit_cmd omits --author flag when author is None."""
    cmd = _build_commit_cmd("msg", None, skip_hooks=True)
    assert all(not arg.startswith("--author") for arg in cmd)


@pytest.fixture()
def _identity_axiom() -> Any:
    """Mock resolve_identity to return an Axiom identity."""
    identity = SimpleNamespace(
        name="Axiom",
        email="axiom@axm-protocol.io",
    )
    with (
        patch(
            "axm_git.hooks.commit_phase.resolve_identity",
            return_value=identity,
        ) as mock_resolve,
        patch(
            "axm_git.hooks.commit_phase.author_args",
            return_value="Axiom <axiom@axm-protocol.io>",
        ) as mock_author_args,
    ):
        yield mock_resolve, mock_author_args


@pytest.fixture()
def _identity_none() -> Any:
    """Mock resolve_identity to return None (no config)."""
    with patch(
        "axm_git.hooks.commit_phase.resolve_identity",
        return_value=None,
    ) as mock_resolve:
        yield mock_resolve


@pytest.fixture()
def _run_git_success() -> Any:
    """Mock run_git to simulate successful operations for _commit_legacy."""

    def _run_git(cmd: list[str], working_dir: Any) -> SimpleNamespace:
        if cmd == ["add", "-A", "."]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[0] == "status":
            return SimpleNamespace(returncode=0, stdout="M file.py\n", stderr="")
        if cmd[0] == "commit":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd == ["rev-parse", "--short", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="abc1234\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch("axm_git.hooks.commit_phase.run_git", side_effect=_run_git) as mock:
        yield mock


@pytest.fixture()
def _commit_from_outputs_deps() -> Any:
    """Mock dependencies for _commit_from_outputs."""

    def _run_git(cmd: list[str], working_dir: Any) -> SimpleNamespace:
        if cmd[0] == "add":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[0] == "ls-files":
            return SimpleNamespace(returncode=0, stdout="file.py\n", stderr="")
        if cmd[0] == "diff":
            return SimpleNamespace(returncode=0, stdout="file.py\n", stderr="")
        if cmd[0] == "commit":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd == ["rev-parse", "--short", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="def5678\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with (
        patch("axm_git.hooks.commit_phase.run_git", side_effect=_run_git) as mock_git,
        patch(
            "axm_git.hooks.commit_phase.find_git_root", return_value=Path("/fake/repo")
        ),
    ):
        yield mock_git


class TestCommitLegacyIdentity:
    """Tests for _commit_legacy with identity resolution."""

    def test_commit_legacy_with_identity(
        self,
        _identity_axiom: Any,
        _run_git_success: Any,
    ) -> None:
        """_commit_legacy passes --author when resolve_identity returns identity."""
        hook = CommitPhaseHook()
        context = {"phase_name": "build"}
        hook._commit_legacy(context, Path("/fake/repo"))

        commit_calls = [
            call
            for call in _run_git_success.call_args_list
            if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert "--author=Axiom <axiom@axm-protocol.io>" in commit_args

    def test_commit_legacy_no_config(
        self,
        _identity_none: Any,
        _run_git_success: Any,
    ) -> None:
        """_commit_legacy omits --author when resolve_identity returns None."""
        hook = CommitPhaseHook()
        context = {"phase_name": "build"}
        hook._commit_legacy(context, Path("/fake/repo"))

        commit_calls = [
            call
            for call in _run_git_success.call_args_list
            if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert all(not arg.startswith("--author") for arg in commit_args)


class TestCommitFromOutputsIdentity:
    """Tests for _commit_from_outputs with identity resolution."""

    def test_commit_from_outputs_with_identity(
        self,
        _identity_axiom: Any,
        _commit_from_outputs_deps: Any,
    ) -> None:
        """_commit_from_outputs passes author when identity is resolved."""
        hook = CommitPhaseHook()
        context = {
            "phase_name": "build",
            "commit_spec": {"files": ["file.py"], "message": "test commit"},
        }
        hook._commit_from_outputs(context, Path("/fake/repo"))

        commit_calls = [
            call
            for call in _commit_from_outputs_deps.call_args_list
            if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert "--author=Axiom <axiom@axm-protocol.io>" in commit_args

    def test_commit_from_outputs_profile_override(
        self,
        _commit_from_outputs_deps: Any,
    ) -> None:
        """_commit_from_outputs passes profile_override to resolve_identity."""
        identity = SimpleNamespace(name="Default", email="default@example.com")
        with (
            patch(
                "axm_git.hooks.commit_phase.resolve_identity",
                return_value=identity,
            ) as mock_resolve,
            patch(
                "axm_git.hooks.commit_phase.author_args",
                return_value="Default <default@example.com>",
            ),
        ):
            hook = CommitPhaseHook()
            context = {
                "phase_name": "build",
                "commit_spec": {"files": ["file.py"], "message": "test commit"},
            }
            hook._commit_from_outputs(context, Path("/fake/repo"), profile="default")

            mock_resolve.assert_called_once()
            call_kwargs = mock_resolve.call_args[1]
            assert call_kwargs["profile_override"] == "default"


class TestHookResultIdentityMetadata:
    """Tests for identity metadata in HookResult."""

    def test_hook_result_includes_identity(
        self,
        _identity_axiom: Any,
        _run_git_success: Any,
    ) -> None:
        """HookResult metadata contains author_name and author_email."""
        hook = CommitPhaseHook()
        context = {"phase_name": "build"}
        result = hook._commit_legacy(context, Path("/fake/repo"))

        assert result.metadata["author_name"] == "Axiom"
        assert result.metadata["author_email"] == "axiom@axm-protocol.io"


class TestIdentityEdgeCases:
    """Edge cases for identity injection."""

    def test_retry_after_autofix_preserves_author(
        self,
        _identity_axiom: Any,
    ) -> None:
        """Retried commit after pre-commit autofix uses same --author flag."""
        first_attempt = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="files were modified by hooks",
        )
        success = SimpleNamespace(returncode=0, stdout="", stderr="")

        call_count = 0

        canned: dict[str, SimpleNamespace] = {
            "add": SimpleNamespace(returncode=0, stdout="", stderr=""),
            "ls-files": SimpleNamespace(returncode=0, stdout="file.py\n", stderr=""),
            "diff": SimpleNamespace(returncode=0, stdout="file.py\n", stderr=""),
        }

        def _run_git(cmd: list[str], working_dir: Any) -> SimpleNamespace:
            nonlocal call_count
            if cmd[0] in canned:
                return canned[cmd[0]]
            if cmd[0] == "commit":
                call_count += 1
                return first_attempt if call_count == 1 else success
            if cmd == ["rev-parse", "--short", "HEAD"]:
                return SimpleNamespace(returncode=0, stdout="abc1234\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with (
            patch(
                "axm_git.hooks.commit_phase.run_git", side_effect=_run_git
            ) as mock_git,
            patch(
                "axm_git.hooks.commit_phase.find_git_root",
                return_value=Path("/fake/repo"),
            ),
        ):
            hook = CommitPhaseHook()
            context = {
                "phase_name": "build",
                "commit_spec": {"files": ["file.py"], "message": "test commit"},
            }
            result = hook._commit_from_outputs(context, Path("/fake/repo"))

            assert result.success
            commit_calls = [
                call for call in mock_git.call_args_list if call[0][0][0] == "commit"
            ]
            assert len(commit_calls) == 2
            for call in commit_calls:
                assert "--author=Axiom <axiom@axm-protocol.io>" in call[0][0]

    def test_legacy_mode_with_profile_override(
        self,
        _run_git_success: Any,
    ) -> None:
        """_commit_legacy respects profile override from params."""
        identity = SimpleNamespace(name="Axiom", email="axiom@axm-protocol.io")
        with (
            patch(
                "axm_git.hooks.commit_phase.resolve_identity",
                return_value=identity,
            ) as mock_resolve,
            patch(
                "axm_git.hooks.commit_phase.author_args",
                return_value="Axiom <axiom@axm-protocol.io>",
            ),
        ):
            hook = CommitPhaseHook()
            context = {"phase_name": "build"}
            hook._commit_legacy(context, Path("/fake/repo"), profile="axiom")

            mock_resolve.assert_called_once()
            call_kwargs = mock_resolve.call_args[1]
            assert call_kwargs["profile_override"] == "axiom"

    def test_missing_config_no_author(
        self,
        _identity_none: Any,
        _run_git_success: Any,
    ) -> None:
        """When no config exists, commits proceed without --author."""
        hook = CommitPhaseHook()
        context = {"phase_name": "build"}
        result = hook._commit_legacy(context, Path("/fake/repo"))

        assert result.success
        commit_calls = [
            call
            for call in _run_git_success.call_args_list
            if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert all(not arg.startswith("--author") for arg in commit_args)


def test_commit_phase_hook_discoverable() -> None:
    from importlib.metadata import entry_points

    eps = entry_points(group="axm.hooks")
    names = [ep.name for ep in eps]
    assert "git:commit-phase" in names


def test_commit_phase_hook_loads() -> None:
    from importlib.metadata import entry_points

    eps = entry_points(group="axm.hooks")
    ep = next(ep for ep in eps if ep.name == "git:commit-phase")
    assert ep.load() is CommitPhaseHook
