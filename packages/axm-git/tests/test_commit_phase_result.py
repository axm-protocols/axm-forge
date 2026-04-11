from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

MODULE = "axm_git.hooks.commit_phase"


@pytest.fixture
def git_root(tmp_path: Path) -> Path:
    return tmp_path


def _git_result(stdout: str = "", stderr: str = "", returncode: int = 0) -> Any:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def _identity(name: str = "Dev", email: str = "dev@test.com") -> Any:
    return SimpleNamespace(name=name, email=email)


# ---------------------------------------------------------------------------
# _build_commit_result — new helper (AC2)
# ---------------------------------------------------------------------------


class TestBuildCommitResult:
    """Tests for the extracted _build_commit_result helper."""

    def test_with_identity_and_warnings(self, git_root: Path) -> None:
        from axm_git.hooks.commit_phase import _build_commit_result

        identity = _identity("Alice", "alice@co.com")
        with patch(f"{MODULE}.run_git", return_value=_git_result(stdout="abc1234\n")):
            result = _build_commit_result(git_root, "feat: add X", identity, ["warn1"])

        assert result.success is True
        assert result.metadata["commit"] == "abc1234"
        assert result.metadata["message"] == "feat: add X"
        assert result.metadata["author_name"] == "Alice"
        assert result.metadata["author_email"] == "alice@co.com"
        assert result.metadata["warnings"] == ["warn1"]

    def test_with_identity_no_warnings(self, git_root: Path) -> None:
        from axm_git.hooks.commit_phase import _build_commit_result

        identity = _identity()
        with patch(f"{MODULE}.run_git", return_value=_git_result(stdout="def5678\n")):
            result = _build_commit_result(git_root, "fix: Y", identity, [])

        assert result.success is True
        assert result.metadata["commit"] == "def5678"
        assert result.metadata["message"] == "fix: Y"
        assert result.metadata["author_name"] == "Dev"
        assert result.metadata["author_email"] == "dev@test.com"
        assert "warnings" not in result.metadata

    def test_without_identity(self, git_root: Path) -> None:
        from axm_git.hooks.commit_phase import _build_commit_result

        with patch(f"{MODULE}.run_git", return_value=_git_result(stdout="aaa1111\n")):
            result = _build_commit_result(git_root, "chore: Z", None, [])

        assert result.success is True
        assert result.metadata["commit"] == "aaa1111"
        assert result.metadata["message"] == "chore: Z"
        assert "author_name" not in result.metadata
        assert "author_email" not in result.metadata

    def test_without_identity_with_warnings(self, git_root: Path) -> None:
        from axm_git.hooks.commit_phase import _build_commit_result

        with patch(f"{MODULE}.run_git", return_value=_git_result(stdout="bbb2222\n")):
            result = _build_commit_result(git_root, "docs: W", None, ["w1", "w2"])

        assert result.success is True
        assert result.metadata["commit"] == "bbb2222"
        assert "author_name" not in result.metadata
        assert result.metadata["warnings"] == ["w1", "w2"]


# ---------------------------------------------------------------------------
# Edge cases through _commit_from_outputs
# ---------------------------------------------------------------------------


def _make_hook() -> Any:
    from axm_git.hooks.commit_phase import CommitPhaseHook

    return CommitPhaseHook()


def _valid_spec(
    files: list[str] | None = None, msg: str = "test commit"
) -> dict[str, Any]:
    return {"files": files or ["a.py"], "message": msg}


class TestCommitFromOutputsEdgeCases:
    """Edge-case coverage for _commit_from_outputs."""

    def test_no_identity_config(self, git_root: Path) -> None:
        """resolve_identity returns None → no --author, no author in result."""
        hook = _make_hook()
        context = {"commit_spec": _valid_spec()}

        with (
            patch(f"{MODULE}.find_git_root", return_value=git_root),
            patch(f"{MODULE}.resolve_identity", return_value=None),
            patch(f"{MODULE}._format_spec_files"),
            patch(f"{MODULE}._stage_spec_files", return_value=None),
            patch(
                f"{MODULE}.run_git",
                side_effect=[
                    _git_result(stdout="a.py\n"),  # diff --cached
                    _git_result(),  # commit
                    _git_result(stdout="ccc3333\n"),  # rev-parse
                ],
            ),
        ):
            result = hook._commit_from_outputs(context, git_root)

        assert result.success is True
        assert result.metadata["commit"] == "ccc3333"
        assert "author_name" not in result.metadata
        assert "author_email" not in result.metadata

    def test_nothing_to_commit(self, git_root: Path) -> None:
        """Staged diff is empty → skipped result."""
        hook = _make_hook()
        context = {"commit_spec": _valid_spec()}

        with (
            patch(f"{MODULE}.find_git_root", return_value=git_root),
            patch(f"{MODULE}.resolve_identity", return_value=None),
            patch(f"{MODULE}._format_spec_files"),
            patch(f"{MODULE}._stage_spec_files", return_value=None),
            patch(f"{MODULE}.run_git", return_value=_git_result(stdout="")),
        ):
            result = hook._commit_from_outputs(context, git_root)

        assert result.success is True
        assert result.metadata.get("skipped") is True
        assert result.metadata["reason"] == "nothing to commit"

    def test_precommit_autofix_retries_once(self, git_root: Path) -> None:
        """First commit fails with 'files were modified' → re-stages + retries."""
        hook = _make_hook()
        context = {"commit_spec": _valid_spec(["b.py"])}

        with (
            patch(f"{MODULE}.find_git_root", return_value=git_root),
            patch(f"{MODULE}.resolve_identity", return_value=_identity()),
            patch(f"{MODULE}._format_spec_files"),
            patch(f"{MODULE}._stage_spec_files", return_value=None),
            patch(
                f"{MODULE}.run_git",
                side_effect=[
                    _git_result(stdout="b.py\n"),  # diff --cached
                    _git_result(
                        returncode=1, stderr="files were modified"
                    ),  # commit fail
                    _git_result(),  # retry commit
                    _git_result(stdout="ddd4444\n"),  # rev-parse
                ],
            ),
        ):
            result = hook._commit_from_outputs(context, git_root)

        assert result.success is True
        assert result.metadata["commit"] == "ddd4444"
