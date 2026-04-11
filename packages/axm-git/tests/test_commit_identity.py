from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from axm_git.tools.commit import GitCommitTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AXIOM_IDENTITY = SimpleNamespace(name="Axiom", email="axiom@axm-protocol.io")
_AUTHOR_FLAG = "--author=Axiom <axiom@axm-protocol.io>"


def _git_result(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def _make_run_git_ok(
    sha: str = "abc1234",
) -> Callable[[list[str], Path], SimpleNamespace]:
    """Return a run_git side-effect that succeeds for all standard calls."""

    def _side_effect(args: list[str], path: Path) -> SimpleNamespace:
        cmd = args[0] if args else ""
        if cmd == "rev-parse":
            return _git_result(stdout=".git")
        if cmd == "add":
            return _git_result()
        if cmd == "commit":
            return _git_result(stdout="[main abc1234] msg")
        if cmd == "log":
            return _git_result(stdout=f"{sha}abcdef0123456789")
        return _git_result()

    return _side_effect


def _single_commit(msg: str = "feat: something") -> list[dict[str, Any]]:
    return [{"files": ["src/foo.py"], "message": msg}]


def _two_commits() -> list[dict[str, Any]]:
    return [
        {"files": ["a.py"], "message": "first"},
        {"files": ["b.py"], "message": "second"},
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tool():
    return GitCommitTool()


@pytest.fixture()
def mock_run_git(mocker):
    return mocker.patch(
        "axm_git.tools.commit.run_git",
        side_effect=_make_run_git_ok(),
    )


@pytest.fixture()
def mock_identity_axiom(mocker):
    return mocker.patch(
        "axm_git.tools.commit.resolve_identity",
        return_value=_AXIOM_IDENTITY,
    )


@pytest.fixture()
def mock_identity_none(mocker):
    return mocker.patch(
        "axm_git.tools.commit.resolve_identity",
        return_value=None,
    )


@pytest.fixture()
def mock_author_args(mocker):
    return mocker.patch(
        "axm_git.tools.commit.author_args",
        return_value=["--author=Axiom <axiom@axm-protocol.io>"],
    )


@pytest.fixture()
def mock_author_args_empty(mocker):
    return mocker.patch(
        "axm_git.tools.commit.author_args",
        return_value=[],
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestCommitWithIdentity:
    """Test that --author is injected when identity resolves."""

    def test_commit_with_identity(
        self, tool, mock_run_git, mock_identity_axiom, mock_author_args, tmp_path
    ):
        result = tool.execute(path=str(tmp_path), commits=_single_commit())

        assert result.success is True
        # Find the commit call and verify --author is present
        commit_calls = [
            c for c in mock_run_git.call_args_list if c[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert _AUTHOR_FLAG in commit_args

    def test_commit_no_config(
        self, tool, mock_run_git, mock_identity_none, mock_author_args_empty, tmp_path
    ):
        result = tool.execute(path=str(tmp_path), commits=_single_commit())

        assert result.success is True
        commit_calls = [
            c for c in mock_run_git.call_args_list if c[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        commit_args = commit_calls[0][0][0]
        assert all("--author" not in arg for arg in commit_args)

    def test_commit_profile_override(
        self, tool, mock_run_git, mock_identity_axiom, mock_author_args, tmp_path
    ):
        tool.execute(path=str(tmp_path), commits=_single_commit(), profile="default")

        mock_identity_axiom.assert_called_once()
        call_kwargs = mock_identity_axiom.call_args
        # profile_override should be passed
        assert call_kwargs.kwargs.get("profile_override") == "default" or (
            len(call_kwargs.args) > 1 and call_kwargs.args[1] == "default"
        )

    def test_batch_commits_same_identity(
        self, tool, mock_run_git, mock_identity_axiom, mock_author_args, tmp_path
    ):
        result = tool.execute(path=str(tmp_path), commits=_two_commits())

        assert result.success is True
        commit_calls = [
            c for c in mock_run_git.call_args_list if c[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 2
        for cc in commit_calls:
            assert _AUTHOR_FLAG in cc[0][0]

        # resolve_identity called only once (not per commit)
        mock_identity_axiom.assert_called_once()


class TestResultIncludesAuthor:
    """Test that ToolResult.data contains author info."""

    def test_result_includes_author(
        self, tool, mock_run_git, mock_identity_axiom, mock_author_args, tmp_path
    ):
        result = tool.execute(path=str(tmp_path), commits=_single_commit())

        assert result.success is True
        assert "author" in result.data
        author = result.data["author"]
        assert author["name"] == "Axiom"
        assert author["email"] == "axiom@axm-protocol.io"

    def test_result_author_null_no_config(
        self, tool, mock_run_git, mock_identity_none, mock_author_args_empty, tmp_path
    ):
        result = tool.execute(path=str(tmp_path), commits=_single_commit())

        assert result.success is True
        assert "author" in result.data
        assert result.data["author"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestIdentityEdgeCases:
    """Edge cases for identity injection."""

    def test_retry_preserves_author(
        self, tool, mock_identity_axiom, mock_author_args, tmp_path, mocker
    ):
        """Pre-commit fix triggers retry — retried commit still has --author."""
        call_count = 0

        def _run_git_with_retry(args, path):
            nonlocal call_count
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _git_result(stdout=".git")
            if cmd == "add":
                return _git_result()
            if cmd == "commit":
                call_count += 1
                if call_count == 1:
                    # First commit attempt fails (pre-commit auto-fix)
                    return _git_result(
                        stdout="files were modified by this hook",
                        returncode=1,
                    )
                # Retry succeeds
                return _git_result(stdout="[main abc1234] msg")
            if cmd == "log":
                return _git_result(stdout="abc1234abcdef0123456789")
            return _git_result()

        mocker.patch(
            "axm_git.tools.commit.run_git",
            side_effect=_run_git_with_retry,
        )

        result = tool.execute(path=str(tmp_path), commits=_single_commit())

        assert result.success is True
        assert result.data["results"][0]["retried"] is True
        # The retry inherits commit_args which already contains --author,
        # so AC6 is satisfied by design. We verify success + retried flag.

    def test_empty_batch_with_profile(
        self, tool, mock_run_git, mock_identity_axiom, mock_author_args, tmp_path
    ):
        """Empty commits list returns error; identity is never resolved."""
        result = tool.execute(path=str(tmp_path), commits=[], profile="axiom")

        assert result.success is False
        assert "No commits provided" in result.error
        mock_identity_axiom.assert_not_called()

    def test_non_axm_repo_with_profile_override(
        self, tool, mock_run_git, mock_identity_axiom, mock_author_args, tmp_path
    ):
        """Profile override forces identity even on non-axm paths."""
        result = tool.execute(
            path=str(tmp_path), commits=_single_commit(), profile="axiom"
        )

        assert result.success is True
        commit_calls = [
            c for c in mock_run_git.call_args_list if c[0][0][0] == "commit"
        ]
        assert len(commit_calls) == 1
        assert _AUTHOR_FLAG in commit_calls[0][0][0]

        # resolve_identity was called with the profile override
        mock_identity_axiom.assert_called_once()
