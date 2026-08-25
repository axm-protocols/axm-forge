from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.release_diff import GitReleaseDiffTool

pytestmark = pytest.mark.integration


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _init_repo(root: Path) -> None:
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t.io"], root)
    _git(["config", "user.name", "t"], root)
    _git(["config", "commit.gpgsign", "false"], root)


def _commit(root: Path, message: str, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", message], root)


def test_diff_since_real_tag_in_tmp_repo(tmp_path: Path) -> None:
    """AC1, AC2, AC3: scoped diff since a real tag in a tmp repo."""
    pkg = tmp_path / "pkg"
    _init_repo(tmp_path)
    _commit(tmp_path, "chore: init", {"pkg/src/pkg/__init__.py": "\n"})
    _git(["tag", "v0.1.0"], tmp_path)
    _commit(tmp_path, "feat: add api", {"pkg/src/pkg/__init__.py": "# api\n"})

    result = GitReleaseDiffTool().execute(path=str(pkg))
    assert result.success
    data = result.data
    assert str(data["current_tag"]).endswith("v0.1.0")
    assert data["suggested_bump"] == "minor"
    assert data["public_api_touched"] is True
    assert data["files_changed"] >= 1


def test_subdir_scoping_excludes_other_package_commits(tmp_path: Path) -> None:
    """AC2: commits touching only package B are not attributed to package A."""
    pkg_a = tmp_path / "pkg_a"
    _init_repo(tmp_path)
    _commit(
        tmp_path,
        "chore: init",
        {"pkg_a/src/a/__init__.py": "\n", "pkg_b/src/b/__init__.py": "\n"},
    )
    _git(["tag", "v0.1.0"], tmp_path)
    _commit(tmp_path, "feat: only b", {"pkg_b/src/b/core.py": "x = 1\n"})

    data = GitReleaseDiffTool().execute(path=str(pkg_a)).data
    assert data["commits_since"] == []
    assert data["suggested_bump"] == "patch"


def test_first_release_full_history(tmp_path: Path) -> None:
    """AC4: no tag -> current_tag None, suggested_next 0.1.0, history summarised."""
    pkg = tmp_path / "pkg"
    _init_repo(tmp_path)
    _commit(tmp_path, "feat: first", {"pkg/src/pkg/__init__.py": "\n"})

    data = GitReleaseDiffTool().execute(path=str(pkg)).data
    assert data["current_tag"] is None
    assert data["suggested_next"] == "0.1.0"
    assert data["commits_since"]


def test_non_git_dir_fails_not_a_false_first_release(tmp_path: Path) -> None:
    """Failure path: a non-git directory is a hard error, not a fake 0.1.0.

    Regression for the P1-1 false-green: without a repo, every read-only git
    call returns empty, which used to masquerade as a clean "first release ->
    0.1.0". The tool must report ``success=False`` instead.
    """
    result = GitReleaseDiffTool().execute(path=str(tmp_path))
    assert not result.success
    assert result.error
    assert result.data is None or result.data.get("suggested_next") != "0.1.0"
