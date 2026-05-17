"""Split from ``test_commit_phase_package_relative.py``."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_git.hooks.commit_phase import CommitPhaseHook


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

        real_run_git = cp.run_git
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
        result = hook.commit_from_outputs(ctx, pkg, skip_hooks=False)

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
