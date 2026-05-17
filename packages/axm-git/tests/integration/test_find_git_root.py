"""Split from ``test_runner.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_git.core.runner import find_git_root


class TestFindGitRoot:
    """Test find_git_root helper."""

    @pytest.mark.parametrize(
        "subpath",
        [
            pytest.param("", id="at_repo_root"),
            pytest.param("deep/nested", id="from_subdirectory"),
        ],
    )
    def test_resolves_repo_root(self, tmp_git_repo: Path, subpath: str) -> None:
        """Returns repo root from the root itself or any nested subdir."""
        start = tmp_git_repo / subpath if subpath else tmp_git_repo
        if subpath:
            start.mkdir(parents=True)
        assert find_git_root(start) == tmp_git_repo

    def test_not_a_repo(self, tmp_path: Path) -> None:
        """Returns None when path is not inside any git repo."""
        assert find_git_root(tmp_path) is None
