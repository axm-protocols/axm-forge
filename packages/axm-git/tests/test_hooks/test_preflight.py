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
