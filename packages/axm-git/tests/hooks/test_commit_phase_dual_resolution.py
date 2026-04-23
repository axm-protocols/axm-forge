"""Integration tests for dual path resolution in commit-phase staging.

Covers AXM-1483: ``_stage_spec_files`` must accept both git-root-relative
and package-relative (working_dir-relative) paths, plus absolute paths
inside the repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from axm_git.hooks.commit_phase import (
    _retry_commit_on_autofix,
    _stage_spec_files,
)


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def _cached_names(git_root: Path) -> str:
    return subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=git_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def workspace_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Init a workspace-style git repo with ``packages/pkg/`` subdir.

    Returns ``(git_root, package_dir)`` where ``package_dir`` is intended
    to be used as ``working_dir`` for the hook.
    """
    _run(["git", "init", "-q", "-b", "main"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    pkg_dir = tmp_path / "packages" / "pkg"
    (pkg_dir / "docs").mkdir(parents=True)
    (pkg_dir / "docs" / "foo.md").write_text("initial\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-q", "-m", "init"], tmp_path)
    return tmp_path, pkg_dir


@pytest.mark.integration
def test_staging_accepts_git_root_relative_path(
    workspace_repo: tuple[Path, Path],
) -> None:
    git_root, pkg_dir = workspace_repo
    (pkg_dir / "docs" / "foo.md").write_text("updated\n")

    err = _stage_spec_files(
        ["packages/pkg/docs/foo.md"],
        git_root,
        working_dir=pkg_dir,
    )

    assert err is None
    assert "packages/pkg/docs/foo.md" in _cached_names(git_root)


@pytest.mark.integration
def test_staging_accepts_package_relative_path(
    workspace_repo: tuple[Path, Path],
) -> None:
    git_root, pkg_dir = workspace_repo
    (pkg_dir / "docs" / "foo.md").write_text("updated\n")

    err = _stage_spec_files(
        ["docs/foo.md"],
        git_root,
        working_dir=pkg_dir,
    )

    assert err is None
    assert "packages/pkg/docs/foo.md" in _cached_names(git_root)


@pytest.mark.integration
def test_staging_accepts_absolute_path_inside_repo(
    workspace_repo: tuple[Path, Path],
) -> None:
    git_root, pkg_dir = workspace_repo
    target = pkg_dir / "docs" / "foo.md"
    target.write_text("updated\n")

    err = _stage_spec_files(
        [str(target)],
        git_root,
        working_dir=pkg_dir,
    )

    assert err is None
    assert "packages/pkg/docs/foo.md" in _cached_names(git_root)


@pytest.mark.integration
def test_staging_rejects_absolute_path_outside_repo(tmp_path: Path) -> None:
    git_root = tmp_path / "repo"
    git_root.mkdir()
    _run(["git", "init", "-q", "-b", "main"], git_root)
    _run(["git", "config", "user.email", "t@e.com"], git_root)
    _run(["git", "config", "user.name", "T"], git_root)
    (git_root / "seed.txt").write_text("seed\n")
    _run(["git", "add", "-A"], git_root)
    _run(["git", "commit", "-q", "-m", "init"], git_root)

    outside = tmp_path / "elsewhere.md"
    outside.write_text("out\n")

    err = _stage_spec_files(
        [str(outside)],
        git_root,
        working_dir=git_root,
    )

    assert err is not None
    assert "outside repository" in err


@pytest.mark.integration
def test_staging_missing_file_error_lists_attempts(
    workspace_repo: tuple[Path, Path],
) -> None:
    git_root, pkg_dir = workspace_repo

    err = _stage_spec_files(
        ["ghost.md"],
        git_root,
        working_dir=pkg_dir,
    )

    assert err is not None
    assert "ghost.md" in err
    assert str(git_root / "ghost.md") in err
    assert str(pkg_dir / "ghost.md") in err


@pytest.mark.integration
def test_retry_on_autofix_uses_dual_resolution(
    workspace_repo: tuple[Path, Path],
) -> None:
    git_root, pkg_dir = workspace_repo
    # Simulate a pre-commit autofix: file was modified on disk by the hook.
    (pkg_dir / "docs" / "foo.md").write_text("autofixed\n")
    first_result = SimpleNamespace(
        returncode=1,
        stdout="",
        stderr="files were modified by this hook",
    )

    result = _retry_commit_on_autofix(
        ["docs/foo.md"],
        ["commit", "-m", "retry", "--no-verify"],
        git_root,
        first_result,
        working_dir=pkg_dir,
    )

    # Restage + commit retry succeeded — if dual resolution had failed,
    # _stage_spec_files would have returned an error and returncode would be 1.
    assert result.returncode == 0, result.stderr
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=git_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "retry" in log
