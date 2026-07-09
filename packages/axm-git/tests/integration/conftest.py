"""Integration fixtures for git_commit hook-restore invariants.

Provide a real git repo under ``tmp_path`` and a parametrisable
``pre-commit`` hook installer (green / failing / autofix-then-green) so the
scoped-restore behaviour of :class:`axm_git.tools.commit.GitCommitTool` can be
exercised against genuine ``git`` output, zero network, never the CWD repo.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

__all__ = ["commit_repo", "install_hook"]


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


# Parametrisable pre-commit hook bodies. ``git`` runs the hook from the repo
# root, so bare relative paths resolve against the worktree top-level.
_HOOK_BODIES: dict[str, str] = {
    # Always accepts the commit.
    "green": "#!/bin/sh\nexit 0\n",
    # Definitively refuses every attempt (no auto-fix marker → no retry).
    "failing": "#!/bin/sh\necho 'hook refused the commit' >&2\nexit 1\n",
    # Rewrites the staged file and fails once with the canonical marker, then
    # (guarded by a sentinel) accepts the retried commit.
    "autofix": (
        "#!/bin/sh\n"
        'sentinel="$(git rev-parse --git-dir)/autofix-done"\n'
        'if [ ! -f "$sentinel" ]; then\n'
        '  touch "$sentinel"\n'
        '  printf "\\n" >> fix_me.py\n'
        '  echo "files were modified by this hook" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    ),
}


@pytest.fixture
def commit_repo(tmp_path: Path) -> Path:
    """A real git repo under ``tmp_path`` with identity + an initial commit."""
    _run(["git", "init", "-q", "-b", "main"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("init\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-q", "-m", "chore: init"], tmp_path)
    return tmp_path


@pytest.fixture
def install_hook(commit_repo: Path) -> Callable[[str], Path]:
    """Install a parametrisable ``pre-commit`` hook; return the repo path.

    The argument selects a hook body from :data:`_HOOK_BODIES`
    (``"green"``, ``"failing"`` or ``"autofix"``).
    """

    def _install(kind: str) -> Path:
        hook = commit_repo / ".git" / "hooks" / "pre-commit"
        hook.write_text(_HOOK_BODIES[kind])
        hook.chmod(0o755)
        return commit_repo

    return _install
