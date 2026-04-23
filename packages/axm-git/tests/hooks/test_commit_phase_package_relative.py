"""Integration tests for package-relative path support in commit_phase staging.

Covers AC1-AC4 of AXM-1483: `_stage_spec_files` must accept both git-root-relative
and package-relative paths (resolved against working_dir), reject absolute paths
outside the repo, and produce diagnostic errors listing every attempted path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_git.hooks.commit_phase import (
    CommitPhaseHook,
    _stage_spec_files,
)

pytestmark = pytest.mark.integration


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def workspace_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Create a git repo at tmp_path with a `packages/pkg/` subdir.

    Returns (git_root, package_dir). The package dir contains a committed
    `docs/foo.md` so downstream tests can target it via either convention.
    """
    git_root = tmp_path
    _run(["git", "init"], git_root)
    _run(["git", "config", "user.email", "test@example.com"], git_root)
    _run(["git", "config", "user.name", "Test"], git_root)

    pkg = git_root / "packages" / "pkg"
    (pkg / "docs").mkdir(parents=True)
    (pkg / "docs" / "foo.md").write_text("hello\n")
    _run(["git", "add", "-A"], git_root)
    _run(["git", "commit", "-m", "init"], git_root)

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


class TestStageSpecFilesPathResolution:
    def test_staging_accepts_git_root_relative_path(
        self, workspace_repo: tuple[Path, Path]
    ) -> None:
        """AC1: path relative to git_root is resolved and staged."""
        git_root, pkg = workspace_repo
        err = _stage_spec_files(
            ["packages/pkg/docs/foo.md"],
            git_root,
            working_dir=pkg,
        )
        assert err is None
        assert "packages/pkg/docs/foo.md" in _cached_files(git_root)

    def test_staging_accepts_package_relative_path(
        self, workspace_repo: tuple[Path, Path]
    ) -> None:
        """AC1: path relative to working_dir (package) is staged."""
        git_root, pkg = workspace_repo
        err = _stage_spec_files(
            ["docs/foo.md"],
            git_root,
            working_dir=pkg,
        )
        assert err is None
        assert "packages/pkg/docs/foo.md" in _cached_files(git_root)

    def test_staging_accepts_absolute_path_inside_repo(
        self, workspace_repo: tuple[Path, Path]
    ) -> None:
        """AC2: absolute path inside git_root is accepted verbatim."""
        git_root, pkg = workspace_repo
        abs_path = str(pkg / "docs" / "foo.md")
        err = _stage_spec_files(
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
        _run(["git", "init"], git_root)
        _run(["git", "config", "user.email", "t@e.com"], git_root)
        _run(["git", "config", "user.name", "T"], git_root)
        (git_root / "seed.txt").write_text("x")
        _run(["git", "add", "-A"], git_root)
        _run(["git", "commit", "-m", "init"], git_root)

        outside = tmp_path / "outside.md"
        outside.write_text("nope")

        err = _stage_spec_files(
            [str(outside)],
            git_root,
            working_dir=git_root,
        )
        assert err is not None
        assert "outside repository" in err.lower()

    def test_staging_missing_file_error_lists_attempts(
        self, workspace_repo: tuple[Path, Path]
    ) -> None:
        """AC3: diagnostic lists every absolute path attempted."""
        git_root, pkg = workspace_repo
        err = _stage_spec_files(
            ["ghost.md"],
            git_root,
            working_dir=pkg,
        )
        assert err is not None
        assert "ghost.md" in err
        assert str(git_root / "ghost.md") in err
        assert str(pkg / "ghost.md") in err


class TestRetryOnAutofixDualResolution:
    def test_retry_on_autofix_uses_dual_resolution(
        self,
        workspace_repo: tuple[Path, Path],
        mocker: Any,
    ) -> None:
        """AC4: retry path re-stages package-relative files after autofix."""
        git_root, pkg = workspace_repo

        # First commit attempt: simulate pre-commit autofix modifying files.
        # Second attempt: succeeds. run_git is used throughout commit_phase.
        from types import SimpleNamespace

        import axm_git.hooks.commit_phase as cp

        real_run_git = cp.run_git  # type: ignore[attr-defined]
        call_log: list[tuple[list[str], ...]] = []
        commit_attempts = {"n": 0}

        def fake_run_git(args: list[str], cwd: Path, *rest: Any, **kw: Any) -> Any:
            call_log.append((args,))
            if args and args[0] == "commit":
                commit_attempts["n"] += 1
                if commit_attempts["n"] == 1:
                    return SimpleNamespace(
                        returncode=1,
                        stdout="",
                        stderr="pre-commit: files were modified by this hook",
                    )
            return real_run_git(args, cwd, *rest, **kw)

        mocker.patch.object(cp, "run_git", side_effect=fake_run_git)

        hook = CommitPhaseHook()
        ctx = {
            "commit_spec": {
                "files": ["docs/foo.md"],  # package-relative
                "message": "test: stage foo",
            }
        }
        result = hook._commit_from_outputs(ctx, pkg, skip_hooks=False)

        assert result.success, getattr(result, "error", None)
        # Two commit attempts means the retry path ran
        assert commit_attempts["n"] == 2
        # And the file landed in history
        log = subprocess.run(
            ["git", "log", "--name-only", "-1", "--pretty="],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "packages/pkg/docs/foo.md" in log
