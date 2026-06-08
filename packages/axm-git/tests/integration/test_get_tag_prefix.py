"""Split from ``test_tag.py``."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.core.semver import compute_bump
from axm_git.tools.tag import get_tag_prefix

# ── Tag prefix regression tests (AXM-371) ────────────────────


class TestGetTagPrefix:
    """Regression tests for get_tag_prefix helper."""

    @pytest.mark.parametrize(
        ("pyproject_content", "expected"),
        [
            pytest.param(
                '[tool.hatch.version]\ntag-pattern = "git/v(?P<version>.*)"\n',
                "git/",
                id="reads_pattern",
            ),
            pytest.param(
                '[tool.hatch.version]\nsource = "vcs"\n',
                "",
                id="no_pattern",
            ),
            pytest.param(None, "", id="no_pyproject"),
        ],
    )
    def test_get_tag_prefix(
        self, tmp_path: Path, pyproject_content: str | None, expected: str
    ) -> None:
        """Resolves prefix from pyproject.toml, empty when missing/absent."""
        if pyproject_content is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject_content)
        assert get_tag_prefix(tmp_path) == expected


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
