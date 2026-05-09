"""Integration test for Bug 1 fix: ``auto_fixed_files`` populated correctly.

When a pre-commit hook auto-fixes files, ``data['failed_commit']
['auto_fixed_files']`` must list those files. Previously the diff was
captured *after* re-staging, which always returned an empty list.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)


def _write_executable(target: Path, script: str) -> None:
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_auto_fixed_files_listed_when_hook_rewrites_then_fails(
    tmp_path: Path,
) -> None:
    """Hook rewrites a file and keeps failing — auto_fixed_files must list it."""
    _init_repo(tmp_path)
    target = tmp_path / "a.txt"
    target.write_text("original\n")

    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    # The hook rewrites a.txt every time and exits non-zero with the
    # "files were modified by this hook" sentinel. The retry loop will
    # therefore re-stage and try again, and fail a second time. The
    # captured ``auto_fixed_files`` must contain ``a.txt``.
    _write_executable(
        hook,
        "#!/bin/sh\n"
        f'echo "rewritten" > "{target}"\n'
        'echo "files were modified by this hook" >&2\n'
        "exit 1\n",
    )

    result = GitCommitTool().execute(
        path=str(tmp_path),
        commits=[{"files": ["a.txt"], "message": "feat: add a"}],
    )

    assert result.success is False
    assert result.data is not None
    failed = result.data.get("failed_commit")
    assert failed is not None, result.data
    assert failed["retried"] is True
    assert failed["auto_fixed_files"], (
        f"expected non-empty auto_fixed_files, got {failed['auto_fixed_files']!r}"
    )
    assert "a.txt" in failed["auto_fixed_files"]
