from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axm_git.core.identity import GitIdentity
from tests_axm_git.integration._helpers import _git_result

MODULE = "axm_git.core.commit_spec"


@pytest.fixture
def git_root(tmp_path: Path) -> Path:
    return tmp_path


def _identity(name: str = "Dev", email: str = "dev@test.com") -> GitIdentity:
    return GitIdentity(name=name, email=email)


class TestBuildCommitResult:
    """Tests for the extracted build_commit_result helper."""

    def test_with_identity_and_warnings(self, git_root: Path) -> None:
        from axm_git.core.commit_spec import build_commit_result

        identity = _identity("Alice", "alice@co.com")
        with patch(f"{MODULE}.run_git", return_value=_git_result(stdout="abc1234\n")):
            result = build_commit_result(git_root, "feat: add X", identity, ["warn1"])

        assert result.success is True
        assert result.metadata["commit"] == "abc1234"
        assert result.metadata["message"] == "feat: add X"
        assert result.metadata["author_name"] == "Alice"
        assert result.metadata["author_email"] == "alice@co.com"
        assert result.metadata["warnings"] == ["warn1"]

    def test_with_identity_no_warnings(self, git_root: Path) -> None:
        from axm_git.core.commit_spec import build_commit_result

        identity = _identity()
        with patch(f"{MODULE}.run_git", return_value=_git_result(stdout="def5678\n")):
            result = build_commit_result(git_root, "fix: Y", identity, [])

        assert result.success is True
        assert result.metadata["commit"] == "def5678"
        assert result.metadata["message"] == "fix: Y"
        assert result.metadata["author_name"] == "Dev"
        assert result.metadata["author_email"] == "dev@test.com"
        assert "warnings" not in result.metadata

    def test_without_identity(self, git_root: Path) -> None:
        from axm_git.core.commit_spec import build_commit_result

        with patch(f"{MODULE}.run_git", return_value=_git_result(stdout="aaa1111\n")):
            result = build_commit_result(git_root, "chore: Z", None, [])

        assert result.success is True
        assert result.metadata["commit"] == "aaa1111"
        assert result.metadata["message"] == "chore: Z"
        assert "author_name" not in result.metadata
        assert "author_email" not in result.metadata

    def test_without_identity_with_warnings(self, git_root: Path) -> None:
        from axm_git.core.commit_spec import build_commit_result

        with patch(f"{MODULE}.run_git", return_value=_git_result(stdout="bbb2222\n")):
            result = build_commit_result(git_root, "docs: W", None, ["w1", "w2"])

        assert result.success is True
        assert result.metadata["commit"] == "bbb2222"
        assert "author_name" not in result.metadata
        assert result.metadata["warnings"] == ["w1", "w2"]
