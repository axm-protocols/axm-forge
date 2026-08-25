"""Split from ``test_get_tag_prefix.py`` — real-git compute_bump coverage."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.core.semver import compute_bump


@pytest.mark.integration
def test_compute_bump_from_real_oneline_log(tmp_path: Path) -> None:
    """AC2: real `git log --oneline` (hash-prefixed) path stays minor."""
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }

    def _git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    _git("init")
    (tmp_path / "a.txt").write_text("x")
    _git("add", "a.txt")
    _git("commit", "-m", "feat: add a")
    oneline = _git("log", "--oneline").strip().splitlines()

    result = compute_bump(oneline, "v0.7.0")
    assert result.bump == "minor"
