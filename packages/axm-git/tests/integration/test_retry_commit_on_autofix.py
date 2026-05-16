"""Split from ``test_commit_phase_dual_resolution.py``."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from axm_git.hooks.commit_phase import _retry_commit_on_autofix


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


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
