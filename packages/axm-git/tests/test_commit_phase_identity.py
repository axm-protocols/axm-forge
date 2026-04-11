from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from axm_git.hooks.commit_phase import _build_commit_cmd

# ---------------------------------------------------------------------------
# Unit tests: _build_commit_cmd with author
# ---------------------------------------------------------------------------


def test_build_commit_cmd_with_author():
    """_build_commit_cmd includes --author flag when author is provided."""
    cmd = _build_commit_cmd(
        "msg", None, skip_hooks=True, author="Axiom <axiom@axm-protocol.io>"
    )
    assert "--author=Axiom <axiom@axm-protocol.io>" in cmd


def test_build_commit_cmd_no_author():
    """_build_commit_cmd omits --author flag when author is None."""
    cmd = _build_commit_cmd("msg", None, skip_hooks=True)
    assert all(not arg.startswith("--author") for arg in cmd)


# ---------------------------------------------------------------------------
# Unit tests: _commit_legacy with identity
# ---------------------------------------------------------------------------


@pytest.fixture()
def _mock_identity_axiom():
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
def _mock_identity_none():
    """Mock resolve_identity to return None (no config)."""
    with patch(
        "axm_git.hooks.commit_phase.resolve_identity",
        return_value=None,
    ) as mock_resolve:
        yield mock_resolve


@pytest.fixture()
def _mock_run_git_success():
    """Mock run_git to simulate successful operations."""

    def _run_git(cmd, working_dir):
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


class TestCommitLegacyIdentity:
    """Tests for _commit_legacy with identity resolution."""

    def test_commit_legacy_with_identity(
        self,
        _mock_identity_axiom,
        _mock_run_git_success,
    ):
        """_commit_legacy passes --author when resolve_identity returns identity."""
        from axm_git.hooks.commit_phase import CommitPhaseHook

        hook = CommitPhaseHook()
        context = {"phase_name": "build"}
        hook._commit_legacy(context, Path("/fake/repo"))

        # Find the commit call
        commit_calls = [
            call
            for call in _mock_run_git_success.call_args_list
            if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert "--author=Axiom <axiom@axm-protocol.io>" in commit_args

    def test_commit_legacy_no_config(
        self,
        _mock_identity_none,
        _mock_run_git_success,
    ):
        """_commit_legacy omits --author when resolve_identity returns None."""
        from axm_git.hooks.commit_phase import CommitPhaseHook

        hook = CommitPhaseHook()
        context = {"phase_name": "build"}
        hook._commit_legacy(context, Path("/fake/repo"))

        # Find the commit call
        commit_calls = [
            call
            for call in _mock_run_git_success.call_args_list
            if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert all(not arg.startswith("--author") for arg in commit_args)


# ---------------------------------------------------------------------------
# Unit tests: _commit_from_outputs with identity
# ---------------------------------------------------------------------------


@pytest.fixture()
def _mock_commit_from_outputs_deps():
    """Mock dependencies for _commit_from_outputs."""

    def _run_git(cmd, working_dir):
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


class TestCommitFromOutputsIdentity:
    """Tests for _commit_from_outputs with identity resolution."""

    def test_commit_from_outputs_with_identity(
        self,
        _mock_identity_axiom,
        _mock_commit_from_outputs_deps,
    ):
        """_commit_from_outputs passes author when identity is resolved."""
        from axm_git.hooks.commit_phase import CommitPhaseHook

        hook = CommitPhaseHook()
        context = {
            "phase_name": "build",
            "commit_spec": {"files": ["file.py"], "message": "test commit"},
        }
        hook._commit_from_outputs(context, Path("/fake/repo"))

        # Find the commit call
        commit_calls = [
            call
            for call in _mock_commit_from_outputs_deps.call_args_list
            if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert "--author=Axiom <axiom@axm-protocol.io>" in commit_args

    def test_commit_from_outputs_profile_override(
        self,
        _mock_commit_from_outputs_deps,
    ):
        """_commit_from_outputs passes profile_override to resolve_identity."""
        from axm_git.hooks.commit_phase import CommitPhaseHook

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


# ---------------------------------------------------------------------------
# Unit tests: HookResult metadata includes identity
# ---------------------------------------------------------------------------


class TestHookResultIdentityMetadata:
    """Tests for identity metadata in HookResult."""

    def test_hook_result_includes_identity(
        self,
        _mock_identity_axiom,
        _mock_run_git_success,
    ):
        """HookResult metadata contains author_name and author_email."""
        from axm_git.hooks.commit_phase import CommitPhaseHook

        hook = CommitPhaseHook()
        context = {"phase_name": "build"}
        result = hook._commit_legacy(context, Path("/fake/repo"))

        assert result.metadata["author_name"] == "Axiom"
        assert result.metadata["author_email"] == "axiom@axm-protocol.io"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestIdentityEdgeCases:
    """Edge cases for identity injection."""

    def test_retry_after_autofix_preserves_author(
        self,
        _mock_identity_axiom,
    ):
        """Retried commit after pre-commit autofix uses same --author flag."""
        from axm_git.hooks.commit_phase import CommitPhaseHook

        first_attempt = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="files were modified by hooks",
        )
        success = SimpleNamespace(returncode=0, stdout="", stderr="")

        call_count = 0

        def _run_git(cmd, working_dir):
            nonlocal call_count
            if cmd[0] == "add":
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if cmd[0] == "ls-files":
                return SimpleNamespace(returncode=0, stdout="file.py\n", stderr="")
            if cmd[0] == "diff":
                return SimpleNamespace(returncode=0, stdout="file.py\n", stderr="")
            if cmd[0] == "commit":
                call_count += 1
                if call_count == 1:
                    return first_attempt
                return success
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
            # Both commit calls should have --author
            commit_calls = [
                call for call in mock_git.call_args_list if call[0][0][0] == "commit"
            ]
            assert len(commit_calls) == 2
            for call in commit_calls:
                assert "--author=Axiom <axiom@axm-protocol.io>" in call[0][0]

    def test_legacy_mode_with_profile_override(
        self,
        _mock_run_git_success,
    ):
        """_commit_legacy respects profile override from params."""
        from axm_git.hooks.commit_phase import CommitPhaseHook

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
        _mock_identity_none,
        _mock_run_git_success,
    ):
        """When no config exists, commits proceed without --author."""
        from axm_git.hooks.commit_phase import CommitPhaseHook

        hook = CommitPhaseHook()
        context = {"phase_name": "build"}
        result = hook._commit_legacy(context, Path("/fake/repo"))

        assert result.success
        commit_calls = [
            call
            for call in _mock_run_git_success.call_args_list
            if call[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert all(not arg.startswith("--author") for arg in commit_args)
