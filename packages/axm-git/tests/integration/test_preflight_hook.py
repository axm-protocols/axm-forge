from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.hooks.preflight import PreflightHook


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one committed file."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "hello.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


@pytest.fixture()
def hook() -> PreflightHook:
    return PreflightHook()


class TestReturnsStatus:
    """Dirty repo with modified tracked + untracked file."""

    def test_returns_status(self, git_repo: Path, hook: PreflightHook) -> None:
        (git_repo / "hello.py").write_text("print('changed')\n")
        (git_repo / "new.txt").write_text("untracked\n")

        result = hook.execute({}, path=str(git_repo))

        assert result.success
        assert result.text is not None
        assert result.text.startswith("git_preflight | 2 files \u00b7 dirty")
        assert "hello.py" in result.text
        assert "new.txt" in result.text


class TestCleanRepo:
    """Clean repo returns compact clean text."""

    def test_clean_repo(self, git_repo: Path, hook: PreflightHook) -> None:
        result = hook.execute({}, path=str(git_repo))

        assert result.success
        assert result.text == "git_preflight | clean"


class TestWorkspacePackageScoped:
    """Scoped to package dir inside workspace."""

    def test_workspace_package_scoped(
        self, tmp_path: Path, hook: PreflightHook
    ) -> None:
        workspace = tmp_path
        subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=workspace,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=workspace,
            check=True,
            capture_output=True,
        )
        pkg = workspace / "packages" / "my-pkg"
        pkg.mkdir(parents=True)
        (pkg / "hello.py").write_text("print('hello')\n")
        (workspace / "root_change.txt").write_text("root\n")
        subprocess.run(
            ["git", "add", "."], cwd=workspace, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=workspace,
            check=True,
            capture_output=True,
        )

        (pkg / "hello.py").write_text("print('changed')\n")
        (workspace / "root_change.txt").write_text("noise\n")

        result = hook.execute({}, path=str(pkg))

        assert result.success
        assert result.text is not None
        assert "hello.py" in result.text
        assert "root_change" not in result.text


class TestTextNoDiffWhenZero:
    """diff_lines=0 suppresses diff but keeps file list."""

    def test_text_no_diff_when_zero(self, git_repo: Path, hook: PreflightHook) -> None:
        (git_repo / "hello.py").write_text("print('changed')\n")

        result = hook.execute({}, path=str(git_repo), diff_lines=0)

        assert result.success
        assert result.text is not None
        assert "hello.py" in result.text
        assert "diff --git" not in result.text


class TestTextIncludesDiffStat:
    """Dirty repo text contains diff stat summary."""

    def test_text_includes_diff_stat(self, git_repo: Path, hook: PreflightHook) -> None:
        (git_repo / "hello.py").write_text("print('changed')\n")

        result = hook.execute({}, path=str(git_repo))

        assert result.success
        assert result.text is not None
        assert "file changed" in result.text or "files changed" in result.text


class TestEdgeCaseOnlyUntracked:
    """Only untracked files — no diff_stat, no diff content."""

    def test_only_untracked(self, git_repo: Path, hook: PreflightHook) -> None:
        (git_repo / "new.txt").write_text("untracked\n")

        result = hook.execute({}, path=str(git_repo))

        assert result.success
        assert result.text is not None
        assert "new.txt" in result.text
        assert "file changed" not in result.text
        assert "files changed" not in result.text
        assert "diff --git" not in result.text


class TestEdgeCaseDiffTruncation:
    """Diff exceeding max_diff_lines triggers truncation marker."""

    def test_diff_truncation(self, git_repo: Path, hook: PreflightHook) -> None:
        big_content = "\n".join(f"line {i}" for i in range(300))
        (git_repo / "hello.py").write_text(big_content)

        result = hook.execute({}, path=str(git_repo), diff_lines=5)

        assert result.success
        assert result.text is not None
        assert result.text.endswith("[diff truncated at 5 lines]")


# ---------------------------------------------------------------------------
# PreflightHook via shared conftest fixtures
# (formerly tests/integration/test_preflight.py)
# ---------------------------------------------------------------------------


class TestPreflightHook:
    """PreflightHook covered via tmp_workspace_repo / tmp_git_repo fixtures."""

    def test_workspace_package_scoped(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Hook scopes status/diff to the package inside a workspace."""
        git_root, pkg_dir = tmp_workspace_repo

        (pkg_dir / "src" / "hello.py").write_text("# modified\n")
        (git_root / "root_change.txt").write_text("workspace noise")

        hook = PreflightHook()
        result = hook.execute({}, path=str(pkg_dir))

        assert result.success
        paths = [f["path"] for f in result.metadata["files"]]
        assert any("hello.py" in p for p in paths)
        assert not any("root_change" in p for p in paths)
        assert result.metadata["file_count"] == 1
        assert result.text is not None
        assert "hello.py" in result.text

    def test_workspace_package_clean(
        self,
        tmp_workspace_repo: tuple[Path, Path],
    ) -> None:
        """Hook reports clean when only workspace root has changes."""
        git_root, pkg_dir = tmp_workspace_repo

        (git_root / "root_change.txt").write_text("noise")

        hook = PreflightHook()
        result = hook.execute({}, path=str(pkg_dir))

        assert result.success
        assert result.metadata["clean"] is True
        assert result.metadata["file_count"] == 0

    def test_returns_status(self, tmp_git_repo: Path) -> None:
        """Hook returns file list and diff for modified files."""
        (tmp_git_repo / ".gitkeep").write_text("modified")
        (tmp_git_repo / "new.txt").write_text("new")

        hook = PreflightHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo)},
        )

        assert result.success
        assert result.metadata["file_count"] == 2
        assert len(result.metadata["files"]) == 2
        assert result.metadata["diff"]
        assert result.metadata["clean"] is False
        assert result.text is not None

    def test_clean_repo(self, tmp_git_repo: Path) -> None:
        """Hook reports clean=True when nothing changed."""
        hook = PreflightHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo)},
        )

        assert result.success
        assert result.metadata["clean"] is True
        assert result.metadata["file_count"] == 0
        assert result.text is not None

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

    def test_no_diff_when_zero_lines(self, tmp_git_repo: Path) -> None:
        """diff_lines=0 suppresses diff content in text."""
        (tmp_git_repo / ".gitkeep").write_text("modified")

        hook = PreflightHook()
        result = hook.execute(
            {"working_dir": str(tmp_git_repo)},
            diff_lines=0,
        )

        assert result.success
        assert result.text is not None
        assert "diff --git" not in result.text

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


# ---------------------------------------------------------------------------
# Entry-point discovery (formerly tests/integration/test_entry_points.py)
# ---------------------------------------------------------------------------


def test_preflight_hook_discoverable() -> None:
    from importlib.metadata import entry_points

    eps = entry_points(group="axm.hooks")
    names = [ep.name for ep in eps]
    assert "git:preflight" in names


def test_preflight_hook_loads() -> None:
    from importlib.metadata import entry_points

    eps = entry_points(group="axm.hooks")
    ep = next(ep for ep in eps if ep.name == "git:preflight")
    assert ep.load() is PreflightHook
