from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.hooks.commit_phase import stage_spec_files


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with an initial commit."""
    _git(["init"], tmp_path)
    _git(["config", "user.email", "test@test.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    (tmp_path / "init.txt").write_text("init")
    _git(["add", "init.txt"], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_deleted_tracked_file_stages_successfully(tmp_path: Path) -> None:
    """A tracked file deleted from disk should stage as a deletion."""
    repo = _init_repo(tmp_path)

    # Create, track, and commit a file, then delete it from disk
    target = repo / "deleted.py"
    target.write_text("content")
    _git(["add", "deleted.py"], repo)
    _git(["commit", "-m", "add deleted.py"], repo)
    target.unlink()

    err = stage_spec_files(["deleted.py"], repo)
    assert err is None

    # Verify the deletion is staged
    status = _git(["diff", "--cached", "--name-only"], repo)
    assert "deleted.py" in status.stdout


def test_nonexistent_file_fails(tmp_path: Path) -> None:
    """A file that was never tracked should produce an error."""
    repo = _init_repo(tmp_path)

    err = stage_spec_files(["never_existed.py"], repo)
    assert err is not None
    assert "never_existed.py" in err


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_mixed_modified_and_deleted_files(tmp_path: Path) -> None:
    """A commit_spec with both modified and deleted files should succeed."""
    repo = _init_repo(tmp_path)

    # Create and commit two files
    (repo / "keep.py").write_text("original")
    (repo / "remove.py").write_text("to delete")
    _git(["add", "keep.py", "remove.py"], repo)
    _git(["commit", "-m", "add files"], repo)

    # Modify one, delete the other
    (repo / "keep.py").write_text("modified")
    (repo / "remove.py").unlink()

    err = stage_spec_files(["keep.py", "remove.py"], repo)
    assert err is None

    # Both changes should be staged
    status = _git(["diff", "--cached", "--name-only"], repo)
    staged = status.stdout.strip().splitlines()
    assert "keep.py" in staged
    assert "remove.py" in staged


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_all_files_deleted(tmp_path: Path) -> None:
    """commit_spec with only deleted files should stage all deletions."""
    repo = _init_repo(tmp_path)

    # Create and commit multiple files, then delete all
    for name in ["a.py", "b.py", "c.py"]:
        (repo / name).write_text(f"content of {name}")
    _git(["add", "a.py", "b.py", "c.py"], repo)
    _git(["commit", "-m", "add files"], repo)

    for name in ["a.py", "b.py", "c.py"]:
        (repo / name).unlink()

    err = stage_spec_files(["a.py", "b.py", "c.py"], repo)
    assert err is None

    status = _git(["diff", "--cached", "--name-only"], repo)
    staged = status.stdout.strip().splitlines()
    assert set(staged) == {"a.py", "b.py", "c.py"}


def test_deleted_then_recreated_file(tmp_path: Path) -> None:
    """A file deleted then recreated should stage normally (exists check passes)."""
    repo = _init_repo(tmp_path)

    target = repo / "revived.py"
    target.write_text("v1")
    _git(["add", "revived.py"], repo)
    _git(["commit", "-m", "add revived.py"], repo)

    # Delete then recreate with different content
    target.unlink()
    target.write_text("v2")

    err = stage_spec_files(["revived.py"], repo)
    assert err is None

    status = _git(["diff", "--cached", "--name-only"], repo)
    assert "revived.py" in status.stdout


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


def _run__from_commit_phase_package_relative(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def workspace_repo__from_commit_phase_package_relative(
    tmp_path: Path,
) -> tuple[Path, Path]:
    """Create a git repo at tmp_path with a `packages/pkg/` subdir.

    Returns (git_root, package_dir). The package dir contains a committed
    `docs/foo.md` so downstream tests can target it via either convention.
    """
    git_root = tmp_path
    _run__from_commit_phase_package_relative(["git", "init"], git_root)
    _run__from_commit_phase_package_relative(
        ["git", "config", "user.email", "test@example.com"], git_root
    )
    _run__from_commit_phase_package_relative(
        ["git", "config", "user.name", "Test"], git_root
    )

    pkg = git_root / "packages" / "pkg"
    (pkg / "docs").mkdir(parents=True)
    (pkg / "docs" / "foo.md").write_text("hello\n")
    _run__from_commit_phase_package_relative(["git", "add", "-A"], git_root)
    _run__from_commit_phase_package_relative(["git", "commit", "-m", "init"], git_root)

    # Modify the file so there's something to stage
    (pkg / "docs" / "foo.md").write_text("hello world\n")
    return git_root, pkg


def _cached_files(git_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=git_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line for line in result.stdout.splitlines() if line}


@pytest.mark.integration
def test_staging_accepts_git_root_relative_path(
    workspace_repo: tuple[Path, Path],
) -> None:
    git_root, pkg_dir = workspace_repo
    (pkg_dir / "docs" / "foo.md").write_text("updated\n")

    err = stage_spec_files(
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

    err = stage_spec_files(
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

    err = stage_spec_files(
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

    err = stage_spec_files(
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

    err = stage_spec_files(
        ["ghost.md"],
        git_root,
        working_dir=pkg_dir,
    )

    assert err is not None
    assert "ghost.md" in err
    assert str(git_root / "ghost.md") in err
    assert str(pkg_dir / "ghost.md") in err


class TestStageSpecFilesPathResolution:
    def test_staging_accepts_git_root_relative_path(
        self, workspace_repo__from_commit_phase_package_relative: tuple[Path, Path]
    ) -> None:
        """AC1: path relative to git_root is resolved and staged."""
        git_root, pkg = workspace_repo__from_commit_phase_package_relative
        err = stage_spec_files(
            ["packages/pkg/docs/foo.md"],
            git_root,
            working_dir=pkg,
        )
        assert err is None
        assert "packages/pkg/docs/foo.md" in _cached_files(git_root)

    def test_staging_accepts_package_relative_path(
        self, workspace_repo__from_commit_phase_package_relative: tuple[Path, Path]
    ) -> None:
        """AC1: path relative to working_dir (package) is staged."""
        git_root, pkg = workspace_repo__from_commit_phase_package_relative
        err = stage_spec_files(
            ["docs/foo.md"],
            git_root,
            working_dir=pkg,
        )
        assert err is None
        assert "packages/pkg/docs/foo.md" in _cached_files(git_root)

    def test_staging_accepts_absolute_path_inside_repo(
        self, workspace_repo__from_commit_phase_package_relative: tuple[Path, Path]
    ) -> None:
        """AC2: absolute path inside git_root is accepted verbatim."""
        git_root, pkg = workspace_repo__from_commit_phase_package_relative
        abs_path = str(pkg / "docs" / "foo.md")
        err = stage_spec_files(
            [abs_path],
            git_root,
            working_dir=pkg,
        )
        assert err is None
        assert "packages/pkg/docs/foo.md" in _cached_files(git_root)

    def test_staging_rejects_absolute_path_outside_repo(self, tmp_path: Path) -> None:
        """AC2: absolute path outside git_root produces a clear error."""
        git_root = tmp_path / "repo"
        git_root.mkdir()
        _run__from_commit_phase_package_relative(["git", "init"], git_root)
        _run__from_commit_phase_package_relative(
            ["git", "config", "user.email", "t@e.com"], git_root
        )
        _run__from_commit_phase_package_relative(
            ["git", "config", "user.name", "T"], git_root
        )
        (git_root / "seed.txt").write_text("x")
        _run__from_commit_phase_package_relative(["git", "add", "-A"], git_root)
        _run__from_commit_phase_package_relative(
            ["git", "commit", "-m", "init"], git_root
        )

        outside = tmp_path / "outside.md"
        outside.write_text("nope")

        err = stage_spec_files(
            [str(outside)],
            git_root,
            working_dir=git_root,
        )
        assert err is not None
        assert "outside repository" in err.lower()

    def test_staging_missing_file_error_lists_attempts(
        self, workspace_repo__from_commit_phase_package_relative: tuple[Path, Path]
    ) -> None:
        """AC3: diagnostic lists every absolute path attempted."""
        git_root, pkg = workspace_repo__from_commit_phase_package_relative
        err = stage_spec_files(
            ["ghost.md"],
            git_root,
            working_dir=pkg,
        )
        assert err is not None
        assert "ghost.md" in err
        assert str(git_root / "ghost.md") in err
        assert str(pkg / "ghost.md") in err
