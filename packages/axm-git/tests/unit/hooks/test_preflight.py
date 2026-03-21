"""Tests for PreflightHook."""

from __future__ import annotations

from pathlib import Path

from axm_git.hooks.preflight import PreflightHook


class TestPreflightHook:
    """Tests for PreflightHook."""

    def test_workspace_package_scoped(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Hook scopes status/diff to the package inside a workspace."""
        git_root, pkg_dir = tmp_workspace_repo

        # Modify a file inside the package
        (pkg_dir / "src" / "hello.py").write_text("# modified\n")
        # Add an unrelated file at workspace root (should be excluded)
        (git_root / "root_change.txt").write_text("workspace noise")

        hook = PreflightHook()
        result = hook.execute({}, path=str(pkg_dir))

        assert result.success
        # Only the package file should appear — not root_change.txt
        paths = [f["path"] for f in result.metadata["files"]]
        assert any("hello.py" in p for p in paths)
        assert not any("root_change" in p for p in paths)
        assert result.metadata["file_count"] == 1

    def test_workspace_package_clean(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Hook reports clean when only workspace root has changes."""
        git_root, pkg_dir = tmp_workspace_repo

        # Change at workspace root only — package is clean
        (git_root / "root_change.txt").write_text("noise")

        hook = PreflightHook()
        result = hook.execute({}, path=str(pkg_dir))

        assert result.success
        assert result.metadata["clean"] is True
        assert result.metadata["file_count"] == 0

    def test_returns_status(self, tmp_git_repo: Path) -> None:
        """Hook returns file list and diff for modified files."""
        # Modify a tracked file to get a diff
        (tmp_git_repo / ".gitkeep").write_text("modified")
        # Add an untracked file
        (tmp_git_repo / "new.txt").write_text("new")

        hook = PreflightHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo)},
        )

        assert result.success
        assert result.metadata["file_count"] == 2
        assert len(result.metadata["files"]) == 2
        assert result.metadata["diff"]  # non-empty (tracked file modified)
        assert result.metadata["clean"] is False

    def test_clean_repo(self, tmp_git_repo: Path) -> None:
        """Hook reports clean=True when nothing changed."""
        hook = PreflightHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo)},
        )

        assert result.success
        assert result.metadata["clean"] is True
        assert result.metadata["file_count"] == 0

    def test_not_a_repo(self, tmp_path: Path) -> None:
        """Hook skips when directory is not a git repo."""
        hook = PreflightHook()
        result = hook.execute(
            {"working_dir": str(tmp_path)},
        )

        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "not a git repo"

    def test_disabled(self, tmp_git_repo: Path) -> None:
        """Hook skips when enabled=False."""
        hook = PreflightHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo)},
            enabled=False,
        )

        assert result.success
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "git disabled"

    def test_preflight_dict_worktree_path(
        self,
        tmp_git_repo: Path,
    ) -> None:
        """Dict worktree_path in context is unwrapped without TypeError."""
        (tmp_git_repo / "f.txt").write_text("x")

        hook = PreflightHook()
        result = hook.execute(
            {
                "worktree_path": {
                    "worktree_path": str(tmp_git_repo),
                    "branch": "feat/x",
                },
            },
        )

        assert result.success
        assert result.metadata["file_count"] == 1

    def test_path_from_params(self, tmp_git_repo: Path) -> None:
        """Hook reads path from params over context working_dir."""
        (tmp_git_repo / "f.txt").write_text("x")

        hook = PreflightHook()
        result = hook.execute(
            {},
            path=str(tmp_git_repo),
        )

        assert result.success
        assert result.metadata["file_count"] == 1
